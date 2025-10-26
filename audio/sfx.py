"""Runtime procedural audio mixer and public API."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pygame

from audio.catalog import EventSpec, SFXCatalog
from audio.logging import log_lines
from audio.recipes import RecipeSpec, SFXRecipes
from audio.renderer import Renderer, RenderResult, db_to_linear
from config import AUDIO_ENABLED

ASSETS_DIR = Path("assets")
CATALOG_FILENAME = "sfx_catalog.json"
RECIPES_FILENAME = "sfx_recipes.json"

BUS_SETTINGS = {
    "ui": {"gain_db": -10.0, "cap": 8},
    "sfx": {"gain_db": -8.0, "cap": 16},
    "loops": {"gain_db": -14.0, "cap": 4},
    "music": {"gain_db": -12.0, "cap": 2},
}


@dataclass
class Voice:
    event: str
    bus: str
    priority: int
    start_time: float
    loop: bool
    channel: Optional[pygame.mixer.Channel]
    sound: Optional[pygame.mixer.Sound]


@dataclass
class BusState:
    name: str
    gain_db: float
    cap: int
    voices: list[Voice] = field(default_factory=list)
    duck_gain_db: float = 0.0
    duck_until: float = 0.0

    def available_channels(self) -> int:
        return max(0, self.cap - len(self.voices))


class SFX:
    """Procedural audio front-end with pygame mixer integration."""

    def __init__(self, enable_audio: bool = True, config_path: Optional[str] = None) -> None:
        log_lines([f"SFX.__init__ enable_audio={enable_audio} config_path={config_path}"])
        self._base_path = Path(config_path) if config_path else ASSETS_DIR
        self._enabled = enable_audio and AUDIO_ENABLED
        self._catalog = SFXCatalog(self._base_path / CATALOG_FILENAME)
        self._recipes = SFXRecipes(self._base_path / RECIPES_FILENAME)
        self._renderer = Renderer()
        self._rng = random.Random()
        self._render_cache: Dict[str, RenderResult] = {}
        self._cooldowns: Dict[str, float] = {}
        self._buses: Dict[str, BusState] = {
            name: BusState(name=name, gain_db=spec["gain_db"], cap=spec["cap"])
            for name, spec in BUS_SETTINGS.items()
        }
        self._loop_voices: Dict[str, Voice] = {}
        self._channels: list[pygame.mixer.Channel] = []
        self._prime_cache()
        if self._enabled:
            self._init_mixer()

    # ------------------------------------------------------------------
    def play(
        self,
        event: str,
        pos: Optional[tuple] = None,
        screen_size: Optional[tuple] = None,
    ) -> bool:
        log_lines([f"SFX.play event={event}"])
        return self._play_event(event, loop_override=False, pos=pos, screen_size=screen_size)

    def play_loop(
        self,
        event: str,
        pos: Optional[tuple] = None,
        screen_size: Optional[tuple] = None,
    ) -> bool:
        log_lines([f"SFX.play_loop event={event}"])
        return self._play_event(event, loop_override=True, pos=pos, screen_size=screen_size)

    def stop_loop(self, event: str) -> None:
        log_lines([f"SFX.stop_loop event={event}"])
        voice = self._loop_voices.pop(event, None)
        if not voice:
            return
        bus = self._buses.get(voice.bus)
        if bus and voice in bus.voices:
            bus.voices.remove(voice)
        if voice.channel:
            voice.channel.stop()

    def duck(self, bus: str, gain_db: float = -6.0, ms: int = 250) -> None:
        log_lines([f"SFX.duck bus={bus} gain_db={gain_db} ms={ms}"])
        bus_state = self._buses.get(bus)
        if not bus_state:
            return
        now = time.monotonic()
        bus_state.duck_gain_db = float(gain_db)
        bus_state.duck_until = max(bus_state.duck_until, now + ms / 1000.0)

    def update(self, dt: float) -> None:
        log_lines([f"SFX.update dt={dt}"])
        now = time.monotonic()
        for bus in self._buses.values():
            if bus.duck_until and now >= bus.duck_until:
                bus.duck_gain_db = 0.0
                bus.duck_until = 0.0
        if not self._enabled:
            for bus in self._buses.values():
                for voice in list(bus.voices):
                    if not voice.loop:
                        bus.voices.remove(voice)
            return
        for bus in self._buses.values():
            for voice in list(bus.voices):
                if not voice.channel:
                    continue
                if not voice.channel.get_busy():
                    bus.voices.remove(voice)
                    if voice.loop and voice.event in self._loop_voices:
                        del self._loop_voices[voice.event]

    # Internal helpers -------------------------------------------------
    def _init_mixer(self) -> None:
        log_lines(["SFX._init_mixer"])
        total_channels = sum(state.cap for state in self._buses.values())
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=self._renderer.sample_rate, channels=2)
        pygame.mixer.set_num_channels(total_channels)
        self._channels = [pygame.mixer.Channel(i) for i in range(total_channels)]

    def _play_event(
        self,
        event: str,
        loop_override: bool,
        pos: Optional[tuple],
        screen_size: Optional[tuple],
    ) -> bool:
        spec = self._catalog.get_spec(event)
        if loop_override and not spec.loop:
            # Force loops when explicitly requested even if catalog loop flag is off.
            loop_flag = True
        else:
            loop_flag = spec.loop
        now = time.monotonic()
        last_play = self._cooldowns.get(event)
        if last_play is not None and (now - last_play) * 1000.0 < spec.cooldown_ms:
            return False
        bus_state = self._buses[spec.bus]
        recipe_id = self._catalog.next_recipe_id(event)
        recipe = self._recipes.get(recipe_id)
        amp_jitter = 1.0 + self._rng.uniform(-spec.vol_jitter, spec.vol_jitter)
        pitch_jitter = self._rng.uniform(-spec.pitch_jitter_semitones, spec.pitch_jitter_semitones)
        render = self._render_recipe(spec, recipe, pitch_jitter, amp_jitter)
        voice = self._allocate_voice(spec, now, loop_flag, render, event, pos, screen_size)
        if not voice:
            return False
        self._cooldowns[event] = now
        if loop_flag:
            self._loop_voices[event] = voice
        return True

    def _prime_cache(self) -> None:
        for recipe in self._recipes.recipes():
            if recipe.recipe_id not in self._render_cache:
                base_rng = random.Random(0)
                self._render_cache[recipe.recipe_id] = self._renderer.render(
                    recipe=recipe,
                    rng=base_rng,
                    pitch_semitones=0.0,
                    amp_scale=1.0,
                )

    def _render_recipe(
        self,
        spec: EventSpec,
        recipe: RecipeSpec,
        pitch_jitter: float,
        amp_jitter: float,
    ) -> RenderResult:
        base_scale = spec.base_gain * amp_jitter
        cached = self._render_cache.get(recipe.recipe_id)
        if (
            cached
            and pitch_jitter == 0.0
            and not recipe.has_randomization
        ):
            data = cached.data.copy() * base_scale
            return RenderResult(data=data, sample_rate=cached.sample_rate)
        return self._renderer.render(
            recipe=recipe,
            rng=self._rng,
            pitch_semitones=pitch_jitter,
            amp_scale=base_scale,
        )

    def _allocate_voice(
        self,
        spec: EventSpec,
        now: float,
        loop_flag: bool,
        render: RenderResult,
        event: str,
        pos: Optional[tuple],
        screen_size: Optional[tuple],
    ) -> Optional[Voice]:
        bus_state = self._buses[spec.bus]
        replacement = self._resolve_voice_limit(bus_state, spec.priority)
        if replacement is False:
            return None
        if isinstance(replacement, Voice):
            self._stop_voice(bus_state, replacement)
        channel = self._claim_channel(bus_state)
        sound = self._make_sound(render)
        voice = Voice(
            event=event,
            bus=spec.bus,
            priority=spec.priority,
            start_time=now,
            loop=loop_flag,
            channel=channel,
            sound=sound,
        )
        bus_state.voices.append(voice)
        if self._enabled and channel and sound:
            left_gain, right_gain = self._pan(spec, pos, screen_size)
            bus_gain = db_to_linear(bus_state.gain_db)
            duck_gain = db_to_linear(bus_state.duck_gain_db)
            final_left = max(0.0, min(1.0, left_gain * bus_gain * duck_gain))
            final_right = max(0.0, min(1.0, right_gain * bus_gain * duck_gain))
            channel.set_volume(final_left, final_right)
            channel.play(sound, loops=-1 if loop_flag else 0)
        return voice

    def _resolve_voice_limit(
        self, bus_state: BusState, priority: int
    ) -> Voice | bool | None:
        if len(bus_state.voices) < bus_state.cap:
            return None
        candidate = min(bus_state.voices, key=lambda v: (v.priority, v.start_time))
        if priority < candidate.priority:
            return False
        return candidate

    def _stop_voice(self, bus_state: BusState, voice: Voice) -> None:
        if voice in bus_state.voices:
            bus_state.voices.remove(voice)
        if voice.loop and voice.event in self._loop_voices:
            del self._loop_voices[voice.event]
        if voice.channel:
            voice.channel.stop()

    def _claim_channel(self, bus_state: BusState) -> Optional[pygame.mixer.Channel]:
        if not self._enabled:
            return None
        for channel in self._channels:
            if not channel.get_busy():
                return channel
        return self._channels[0] if self._channels else None

    def _make_sound(self, render: RenderResult) -> Optional[pygame.mixer.Sound]:
        if not self._enabled:
            return None
        array = np.clip(render.data, -1.0, 1.0)
        int_data = (array * 32767).astype(np.int16)
        return pygame.sndarray.make_sound(int_data.copy())

    def _pan(
        self,
        spec: EventSpec,
        pos: Optional[tuple],
        screen_size: Optional[tuple],
    ) -> Tuple[float, float]:
        if not spec.pan or not pos or not screen_size:
            return (math.sqrt(0.5), math.sqrt(0.5))
        width = float(screen_size[0]) if screen_size[0] else 1.0
        x_norm = max(0.0, min(1.0, float(pos[0]) / width))
        pan = (x_norm * 2.0) - 1.0
        # Equal-power panning: convert normalized pan (-1..+1) into theta ∈ [0, π/2]
        # and distribute gains via cos/sin so center energy matches edges.
        theta = (pan + 1.0) * (math.pi / 4.0)
        left = math.cos(theta)
        right = math.sin(theta)
        return left, right
