"""Runtime mixer and public API for procedural audio."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pygame
import pygame.sndarray

from config import AUDIO_ENABLED

from ._logging import log_line
from .catalog import Catalog, EventSpec
from .recipes import RecipeLibrary
from .renderer import RenderedSound, Renderer, SAMPLE_RATE

BusName = str


@dataclass
class Voice:
    event: str
    bus: BusName
    priority: int
    started_at: float
    sound: Optional[pygame.mixer.Sound] = None
    channel: Optional[pygame.mixer.Channel] = None
    loop: bool = False
    duration: float = 0.0


@dataclass
class BusState:
    gain_db: float
    cap: int
    voices: list[Voice] = field(default_factory=list)
    duck_gain: float = 1.0
    duck_end: float = 0.0

    @property
    def gain_linear(self) -> float:
        return 10 ** (self.gain_db / 20.0)


class SFX:
    """High-level sound effect controller."""

    _BUSES: Dict[BusName, tuple[float, int]] = {
        "ui": (-10.0, 8),
        "sfx": (-8.0, 16),
        "loops": (-14.0, 4),
        "music": (-12.0, 2),
    }

    def __init__(self, enable_audio: bool = True, config_path: Optional[str] = None) -> None:
        self._enable_audio = enable_audio and AUDIO_ENABLED
        self._renderer = Renderer()
        root = Path(config_path) if config_path else Path(".")
        self._catalog = Catalog.load_default(root)
        self._recipes = RecipeLibrary.load_default(root)
        self._render_cache: Dict[str, RenderedSound] = {}
        self._variant_index: Dict[str, int] = {}
        self._cooldowns: Dict[str, float] = {}
        self._buses: Dict[BusName, BusState] = {
            name: BusState(gain_db=gain_db, cap=cap) for name, (gain_db, cap) in self._BUSES.items()
        }
        self._loops: Dict[str, Voice] = {}
        self._last_update = time.monotonic()
        if self._enable_audio and not pygame.mixer.get_init():
            pygame.mixer.init(frequency=SAMPLE_RATE, channels=2)
        log_line("initialized", context="SFX", data={"audio": self._enable_audio})

    def play(self, event: str, pos: Optional[tuple] = None, screen_size: Optional[tuple] = None) -> bool:
        """Play a one-shot event."""
        return self._trigger(event, loop=False, pos=pos, screen_size=screen_size)

    def play_loop(self, event: str, pos: Optional[tuple] = None, screen_size: Optional[tuple] = None) -> bool:
        """Start or refresh a looped event."""
        if event in self._loops:
            voice = self._loops[event]
            self._apply_pan(voice, pos, screen_size)
            return True
        return self._trigger(event, loop=True, pos=pos, screen_size=screen_size)

    def stop_loop(self, event: str) -> None:
        voice = self._loops.pop(event, None)
        if not voice:
            return
        log_line("stop_loop", context="SFX", data={"event": event})
        self._stop_voice(voice)

    def duck(self, bus: str, gain_db: float = -6.0, ms: int = 250) -> None:
        if bus not in self._buses:
            raise KeyError(f"Unknown bus '{bus}'")
        state = self._buses[bus]
        state.duck_gain = 10 ** (gain_db / 20.0)
        state.duck_end = time.monotonic() + ms / 1000.0
        log_line("duck", context="SFX", data={"bus": bus, "gain_db": gain_db, "ms": ms})

    def update(self, dt: float) -> None:
        now = time.monotonic()
        for bus in self._buses.values():
            if bus.duck_gain < 1.0 and now >= bus.duck_end:
                bus.duck_gain = 1.0
            for voice in list(bus.voices):
                if voice.loop:
                    continue
                if self._enable_audio and voice.channel:
                    if not voice.channel.get_busy():
                        self._stop_voice(voice)
                elif now - voice.started_at >= voice.duration:
                    self._stop_voice(voice)
        self._last_update = now

    def _trigger(self, event: str, *, loop: bool, pos: Optional[tuple], screen_size: Optional[tuple]) -> bool:
        spec = self._catalog.get_spec(event)
        now = time.monotonic()
        ready_at = self._cooldowns.get(event, 0.0)
        if now < ready_at:
            log_line("cooldown", context="SFX", data={"event": event})
            return False
        self._cooldowns[event] = now + spec.cooldown_ms / 1000.0
        recipe_id = self._next_variant(spec)
        rendered = self._render_recipe(recipe_id)
        volume_scale = self._volume_jitter(spec)
        pitch_ratio = self._pitch_jitter(spec)
        buffer = self._prepare_buffer(rendered, volume_scale, pitch_ratio)
        bus_state = self._buses[spec.bus]
        total_gain = spec.base_gain * bus_state.gain_linear * bus_state.duck_gain
        buffer *= total_gain
        left, right = self._pan_gains(spec, pos, screen_size)
        buffer[:, 0] *= left
        buffer[:, 1] *= right
        voice = Voice(event=event, bus=spec.bus, priority=spec.priority, started_at=now, loop=loop)
        if not self._start_voice(voice, buffer, loop):
            return False
        if loop:
            self._loops[event] = voice
        log_line("play", context="SFX", data={"event": event, "loop": loop, "bus": spec.bus})
        return True

    def _start_voice(self, voice: Voice, buffer: np.ndarray, loop: bool) -> bool:
        bus = self._buses[voice.bus]
        if len(bus.voices) >= bus.cap:
            loser = min(bus.voices, key=lambda v: (v.priority, v.started_at))
            if voice.priority < loser.priority:
                log_line("drop", context="SFX", data={"event": voice.event, "reason": "priority"})
                return False
            self._stop_voice(loser)
            self._loops.pop(loser.event, None)
        sound = None
        channel = None
        if self._enable_audio:
            int_buffer = np.clip(buffer, -1.0, 1.0)
            int_buffer = (int_buffer * 32767).astype(np.int16)
            sound = pygame.sndarray.make_sound(int_buffer.copy())
            loops = -1 if loop else 0
            channel = sound.play(loops=loops)
        voice.sound = sound
        voice.channel = channel
        voice.duration = buffer.shape[0] / SAMPLE_RATE
        bus.voices.append(voice)
        return True

    def _stop_voice(self, voice: Voice) -> None:
        bus = self._buses[voice.bus]
        if voice in bus.voices:
            bus.voices.remove(voice)
        if self._loops.get(voice.event) is voice:
            self._loops.pop(voice.event, None)
        if voice.channel:
            voice.channel.stop()
        if voice.sound:
            voice.sound.fadeout(0)

    def _render_recipe(self, recipe_id: str) -> RenderedSound:
        cached = self._render_cache.get(recipe_id)
        if cached is not None:
            return cached
        recipe = self._recipes.get(recipe_id)
        rendered = self._renderer.render(recipe)
        self._render_cache[recipe_id] = rendered
        return rendered

    def _prepare_buffer(self, rendered: RenderedSound, volume_scale: float, pitch_ratio: float) -> np.ndarray:
        buffer = rendered.buffer.copy()
        if pitch_ratio != 1.0:
            buffer = self._resample(buffer, pitch_ratio)
        buffer *= volume_scale
        return buffer

    def _resample(self, buffer: np.ndarray, ratio: float) -> np.ndarray:
        if ratio <= 0:
            return buffer
        length = buffer.shape[0]
        new_length = max(1, int(length / ratio))
        positions = np.linspace(0, length - 1, new_length)
        left = np.interp(positions, np.arange(length), buffer[:, 0])
        right = np.interp(positions, np.arange(length), buffer[:, 1])
        return np.stack([left, right], axis=1)

    def _next_variant(self, spec: EventSpec) -> str:
        idx = self._variant_index.get(spec.name, 0)
        recipe_id = spec.recipe_ids[idx]
        self._variant_index[spec.name] = (idx + 1) % len(spec.recipe_ids)
        return recipe_id

    def _volume_jitter(self, spec: EventSpec) -> float:
        jitter = spec.vol_jitter
        if jitter <= 0:
            return 1.0
        delta = np.random.uniform(-jitter, jitter)
        return max(0.0, 1.0 + delta)

    def _pitch_jitter(self, spec: EventSpec) -> float:
        jitter = spec.pitch_jitter_semitones
        if jitter <= 0:
            return 1.0
        delta = np.random.uniform(-jitter, jitter)
        return 2 ** (delta / 12.0)

    def _pan_gains(self, spec: EventSpec, pos: Optional[tuple], screen_size: Optional[tuple]) -> Tuple[float, float]:
        if not spec.pan or not pos or not screen_size:
            return 1.0, 1.0
        x, _ = pos
        width, _ = screen_size
        if width <= 0:
            return 1.0, 1.0
        norm = max(-1.0, min(1.0, (x / width) * 2.0 - 1.0))
        theta = (norm + 1.0) * (math.pi / 4.0)
        # Equal-power panning keeps the center energy consistent.
        return math.cos(theta), math.sin(theta)

    def _apply_pan(self, voice: Voice, pos: Optional[tuple], screen_size: Optional[tuple]) -> None:
        spec = self._catalog.get_spec(voice.event)
        left, right = self._pan_gains(spec, pos, screen_size)
        if voice.channel:
            voice.channel.set_volume(left, right)
