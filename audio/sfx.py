"""Runtime sound effect mixer and API."""

from __future__ import annotations

import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pygame

from config import AUDIO_ENABLED, WIDTH, HEIGHT
from .catalog import EventCatalog, EventSpec
from .recipes import RecipeLibrary
from .renderer import Renderer
from .utils import SAMPLE_RATE, clamp, db_to_gain, log_debug


BUS_CONFIG = {
    "ui": {"base_gain_db": -10.0, "cap": 8},
    "sfx": {"base_gain_db": -8.0, "cap": 16},
    "loops": {"base_gain_db": -14.0, "cap": 4},
    "music": {"base_gain_db": -12.0, "cap": 2},
}


@dataclass
class Voice:
    bus: str
    event: str
    priority: int
    start_time: float
    channel_index: int


class SFX:
    """Public audio API used by gameplay systems."""

    def __init__(self, enable_audio: bool = True, config_path: Optional[str] = None) -> None:
        self._enabled = enable_audio and AUDIO_ENABLED
        base_path = Path(config_path) if config_path else Path("assets")
        catalog_path = base_path / "sfx_catalog.json"
        recipe_path = base_path / "sfx_recipes.json"
        log_debug(f"sfx:init enabled={self._enabled} base={base_path}")
        self._catalog = EventCatalog(catalog_path)
        self._recipes = RecipeLibrary(recipe_path)
        self._renderer = Renderer(self._recipes)
        self._cooldowns: Dict[str, float] = defaultdict(lambda: -1e9)
        self._loop_channels: Dict[str, int] = {}
        self._voices: Dict[int, Voice] = {}
        self._bus_channels: Dict[str, set[int]] = {bus: set() for bus in BUS_CONFIG}
        self._ducking: Dict[str, Tuple[float, float]] = {bus: (0.0, 0.0) for bus in BUS_CONFIG}
        self._time = time.monotonic()
        self._sounds: Dict[int, pygame.mixer.Sound] = {}
        self._screen_size = (WIDTH, HEIGHT)
        self._channels: list[pygame.mixer.Channel] = []

        if self._enabled:
            self._init_mixer()
        else:
            log_debug("sfx:init mixer disabled")

    def _init_mixer(self) -> None:
        total_channels = sum(cfg["cap"] for cfg in BUS_CONFIG.values())
        pygame.mixer.pre_init(SAMPLE_RATE, size=-16, channels=2)
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)
        pygame.mixer.set_num_channels(total_channels)
        self._channels = [pygame.mixer.Channel(i) for i in range(total_channels)]
        log_debug(f"sfx:mixer channels={total_channels}")

    def play(self, event: str, pos: Optional[tuple] = None, screen_size: Optional[tuple] = None) -> bool:
        """Play a one-shot sound event."""

        return self._play(event, loop_override=False, pos=pos, screen_size=screen_size)

    def play_loop(self, event: str, pos: Optional[tuple] = None, screen_size: Optional[tuple] = None) -> bool:
        """Start (or refresh) a looping event."""

        return self._play(event, loop_override=True, pos=pos, screen_size=screen_size)

    def stop_loop(self, event: str) -> None:
        """Stop a looping event if active."""

        if event in self._loop_channels:
            channel_index = self._loop_channels.pop(event)
            if self._enabled:
                channel = self._channels[channel_index]
                channel.stop()
            self._release_voice(channel_index)
            log_debug(f"sfx:stop_loop event={event}")

    def duck(self, bus: str, gain_db: float = -6.0, ms: int = 250) -> None:
        """Temporarily attenuate a bus to create a side-chain duck window."""

        if bus not in self._ducking:
            return
        end_time = self._time + ms / 1000.0
        self._ducking[bus] = (gain_db, end_time)
        log_debug(f"sfx:duck bus={bus} gain={gain_db} end={end_time:.3f}")

    def update(self, dt: float) -> None:
        """Advance timers and clean up finished voices."""

        self._time += dt
        for bus, (gain_db, end_time) in list(self._ducking.items()):
            if self._time > end_time:
                self._ducking[bus] = (0.0, self._time)
        if not self._enabled:
            return
        for idx, channel in enumerate(self._channels):
            if not channel.get_busy() and idx in self._voices:
                self._release_voice(idx)

    # Internal helpers -------------------------------------------------

    def _play(self, event: str, loop_override: bool, pos: Optional[tuple], screen_size: Optional[tuple]) -> bool:
        spec = self._catalog.get_spec(event)
        now = self._time or time.monotonic()
        elapsed = (now - self._cooldowns[event]) * 1000.0
        if elapsed < spec.cooldown_ms and not loop_override:
            log_debug(f"sfx:cooldown event={event} remaining={spec.cooldown_ms - elapsed:.1f}ms")
            return False
        self._cooldowns[event] = now

        recipe_id = self._catalog.next_variant(event)
        pitch_jitter = random.uniform(-spec.pitch_jitter_semitones, spec.pitch_jitter_semitones)
        amp_jitter = 1 + random.uniform(-spec.vol_jitter, spec.vol_jitter)
        buffer = self._renderer.render(recipe_id, pitch_semitones=pitch_jitter, amp_multiplier=amp_jitter)

        gains = self._pan(spec, pos, screen_size)
        buffer[:, 0] *= gains[0]
        buffer[:, 1] *= gains[1]

        bus_gain = db_to_gain(BUS_CONFIG[spec.bus]["base_gain_db"])
        duck_gain = db_to_gain(self._ducking[spec.bus][0])
        buffer *= spec.base_gain * bus_gain * duck_gain

        if not self._enabled:
            log_debug(f"sfx:simulate event={event}")
            return True

        channel_index = self._allocate_channel(spec.bus, spec.priority)
        if channel_index is None:
            log_debug(f"sfx:drop event={event} bus={spec.bus} (no channel)")
            return False

        sound_array = np.clip(buffer, -1.0, 1.0)
        sound = pygame.sndarray.make_sound((sound_array * 32767).astype(np.int16))
        loops = -1 if (loop_override or spec.loop) else 0
        self._channels[channel_index].play(sound, loops=loops)
        self._register_voice(channel_index, spec.bus, event, spec.priority)
        self._sounds[channel_index] = sound
        if loop_override or spec.loop:
            self._loop_channels[event] = channel_index
        log_debug(f"sfx:play event={event} bus={spec.bus} channel={channel_index}")
        return True

    def _pan(self, spec: EventSpec, pos: Optional[tuple], screen_size: Optional[tuple]) -> Tuple[float, float]:
        if not spec.pan or pos is None:
            return (math.sqrt(0.5), math.sqrt(0.5))
        screen = screen_size or self._screen_size
        norm_x = clamp((pos[0] / max(screen[0], 1)) * 2 - 1, -1.0, 1.0)
        theta = (norm_x + 1) * (math.pi / 4)
        # Equal-power panning keeps perceived loudness consistent.
        left = math.cos(theta)
        right = math.sin(theta)
        return (left, right)

    def _allocate_channel(self, bus: str, priority: int) -> Optional[int]:
        cap = BUS_CONFIG[bus]["cap"]
        active = self._bus_channels[bus]
        if len(active) < cap:
            for idx, channel in enumerate(self._channels):
                if not channel.get_busy() and idx not in self._voices:
                    return idx
        # Bus full – find lowest priority, oldest voice.
        if not active:
            return None
        candidate_index = min(
            active,
            key=lambda idx: (self._voices[idx].priority, self._voices[idx].start_time),
        )
        candidate_voice = self._voices[candidate_index]
        if candidate_voice.priority > priority:
            return None
        self._channels[candidate_index].stop()
        self._release_voice(candidate_index)
        return candidate_index

    def _register_voice(self, channel_index: int, bus: str, event: str, priority: int) -> None:
        voice = Voice(bus=bus, event=event, priority=priority, start_time=self._time, channel_index=channel_index)
        self._voices[channel_index] = voice
        self._bus_channels[bus].add(channel_index)

    def _release_voice(self, channel_index: int) -> None:
        if channel_index in self._voices:
            voice = self._voices.pop(channel_index)
            self._bus_channels[voice.bus].discard(channel_index)
        self._sounds.pop(channel_index, None)


__all__ = ["SFX"]
