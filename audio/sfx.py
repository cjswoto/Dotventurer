"""Runtime SFX mixer and public API."""
from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np

from config import AUDIO_ENABLED, AUDIO_LOG_ENABLED
from .catalog import Catalog, EventSpec, load_catalog
from .recipes import RecipeLibrary, load_recipes
from .renderer import RecipeRenderer, RenderResult, SAMPLE_RATE, semitone_ratio

try:  # pragma: no cover - optional dependency
    import pygame
    import pygame.sndarray
except Exception:  # pragma: no cover - handled via feature flag
    pygame = None

ASSETS_DIR = "assets"
CATALOG_NAME = "sfx_catalog.json"
RECIPES_JSON = "sfx_recipes.json"
RECIPES_YAML = "sfx_recipes.yaml"


@dataclass
class BusState:
    name: str
    gain_db: float
    cap: int
    voices: list = field(default_factory=list)
    duck_gain: float = 1.0
    duck_until: float = 0.0

    @property
    def base_gain(self) -> float:
        return db_to_linear(self.gain_db)


@dataclass
class Voice:
    event: str
    bus: str
    priority: int
    started_at: float
    loop: bool
    sound: Optional["pygame.mixer.Sound"]
    channel: Optional["pygame.mixer.Channel"]


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _log(message: str) -> None:
    if not AUDIO_LOG_ENABLED:
        return
    os.makedirs("logs", exist_ok=True)
    with open("logs/debug.txt", "a", encoding="utf-8") as handle:
        handle.write(f"[{_timestamp()}][sfx] {message}\n")


def db_to_linear(value: float) -> float:
    return 10 ** (value / 20.0)


class SFX:
    """High level API exposed to gameplay systems."""

    def __init__(self, enable_audio: bool = True, config_path: Optional[str] = None):
        self.enable_audio = enable_audio and AUDIO_ENABLED and pygame is not None
        self.assets_path = config_path or ASSETS_DIR
        self.catalog = self._load_catalog()
        self.recipes = self._load_recipes()
        self.renderer = RecipeRenderer(self.recipes)
        self._render_cache: Dict[str, RenderResult] = {}
        self._event_last_play: Dict[str, float] = {}
        self._buses = {
            "ui": BusState("ui", -10.0, 8),
            "sfx": BusState("sfx", -8.0, 16),
            "loops": BusState("loops", -14.0, 4),
            "music": BusState("music", -12.0, 2),
        }
        self._loops: Dict[str, Voice] = {}
        self._now = time.monotonic
        if self.enable_audio:
            self._init_audio()
        _log("SFX system initialised")

    def play(self, event: str, pos: Optional[tuple] = None, screen_size: Optional[tuple] = None):
        _log(f"play request event={event}")
        spec = self.catalog.get_spec(event)
        if self._cooldown_active(spec):
            _log(f"cooldown active for {event}")
            return
        recipe_id = spec.next_recipe_id()
        if recipe_id is None:
            _log(f"no recipe for event {event}")
            return
        base_buffer = self._get_buffer(recipe_id)
        jittered = self._apply_jitter(base_buffer, spec)
        panned = self._apply_pan(jittered, spec.pan, pos, screen_size)
        self._start_voice(event, spec, panned, loop=False)
        self._event_last_play[spec.name] = self._now()

    def play_loop(self, event: str, pos: Optional[tuple] = None, screen_size: Optional[tuple] = None):
        _log(f"play_loop request event={event}")
        spec = self.catalog.get_spec(event)
        if event in self._loops:
            _log(f"loop already active for {event}")
            return
        recipe_id = spec.next_recipe_id()
        if recipe_id is None:
            return
        base_buffer = self._get_buffer(recipe_id)
        jittered = self._apply_jitter(base_buffer, spec)
        panned = self._apply_pan(jittered, spec.pan, pos, screen_size)
        voice = self._start_voice(event, spec, panned, loop=True)
        if voice:
            self._loops[event] = voice

    def stop_loop(self, event: str):
        _log(f"stop_loop event={event}")
        voice = self._loops.pop(event, None)
        if voice and voice.channel:
            voice.channel.stop()
        if voice and voice.bus in self._buses:
            self._remove_voice(voice)

    def duck(self, bus: str, gain_db: float = -6.0, ms: int = 250):
        _log(f"duck bus={bus} gain={gain_db}ms duration={ms}")
        if bus not in self._buses:
            raise KeyError(f"Unknown bus '{bus}'")
        bus_state = self._buses[bus]
        bus_state.duck_gain = db_to_linear(gain_db)
        bus_state.duck_until = self._now() + ms / 1000.0

    def update(self, dt: float):
        _log(f"update dt={dt}")
        current_time = self._now()
        for bus_state in self._buses.values():
            if bus_state.duck_until and current_time >= bus_state.duck_until:
                _log(f"duck expired for bus={bus_state.name}")
                bus_state.duck_gain = 1.0
                bus_state.duck_until = 0.0
        self._cleanup_finished_voices()

    # internal helpers
    def _init_audio(self) -> None:
        _log("initialising pygame mixer")
        if pygame is None:
            return
        pygame.mixer.pre_init(SAMPLE_RATE, size=-16, channels=2)
        pygame.mixer.init()

    def _load_catalog(self) -> Catalog:
        catalog_path = os.path.join(self.assets_path, CATALOG_NAME)
        return load_catalog(catalog_path)

    def _load_recipes(self) -> RecipeLibrary:
        json_path = os.path.join(self.assets_path, RECIPES_JSON)
        yaml_path = os.path.join(self.assets_path, RECIPES_YAML)
        if os.path.exists(json_path):
            return load_recipes(json_path)
        if os.path.exists(yaml_path):
            return load_recipes(yaml_path)
        raise FileNotFoundError("No recipe file found")

    def _cooldown_active(self, spec: EventSpec) -> bool:
        last_time = self._event_last_play.get(spec.name)
        if last_time is None:
            return False
        elapsed_ms = (self._now() - last_time) * 1000.0
        return elapsed_ms < spec.cooldown_ms

    def _get_buffer(self, recipe_id: str) -> np.ndarray:
        if recipe_id not in self._render_cache:
            self._render_cache[recipe_id] = self.renderer.render(recipe_id)
        return self._render_cache[recipe_id].buffer.copy()

    def _apply_jitter(self, buffer: np.ndarray, spec: EventSpec) -> np.ndarray:
        amp_jitter = 1 + np.random.uniform(-spec.vol_jitter, spec.vol_jitter)
        buffer = buffer * amp_jitter
        pitch_offset = np.random.uniform(-spec.pitch_jitter_semitones, spec.pitch_jitter_semitones)
        if abs(pitch_offset) < 1e-4:
            return buffer
        ratio = semitone_ratio(pitch_offset)
        return self._resample(buffer, ratio)

    def _resample(self, buffer: np.ndarray, ratio: float) -> np.ndarray:
        if ratio <= 0:
            return buffer
        frames = buffer.shape[0]
        new_frames = max(1, int(frames / ratio))
        positions = np.linspace(0, frames - 1, new_frames, dtype=np.float32)
        output = np.zeros((new_frames, buffer.shape[1]), dtype=buffer.dtype)
        indices = np.arange(frames, dtype=np.float32)
        for channel in range(buffer.shape[1]):
            output[:, channel] = np.interp(positions, indices, buffer[:, channel])
        return output

    def _apply_pan(
        self,
        buffer: np.ndarray,
        should_pan: bool,
        pos: Optional[tuple],
        screen_size: Optional[tuple],
    ) -> np.ndarray:
        if not should_pan or pos is None or screen_size is None:
            return buffer
        width = screen_size[0] or 1
        pan = (pos[0] / width) * 2 - 1
        pan = max(-1.0, min(1.0, pan))
        # Constant-power panning keeps center energy consistent by mapping pan -> angle
        # across [0, π/2] then using cos/sin for left/right gains (CMU SCS guidance).
        angle = (pan + 1) * (math.pi / 4)
        left = math.cos(angle)
        right = math.sin(angle)
        _log(f"pan pos={pos} screen={screen_size} gains=({left:.2f},{right:.2f})")
        buffer[:, 0] *= left
        buffer[:, 1] *= right
        return buffer

    def _start_voice(self, event: str, spec: EventSpec, buffer: np.ndarray, loop: bool) -> Optional[Voice]:
        bus_state = self._buses[spec.bus]
        gain = bus_state.base_gain * bus_state.duck_gain * spec.base_gain
        buffer = np.clip(buffer * gain, -1.0, 1.0)
        voice = Voice(
            event=event,
            bus=spec.bus,
            priority=spec.priority,
            started_at=self._now(),
            loop=loop,
            sound=None,
            channel=None,
        )
        if self.enable_audio and pygame is not None:
            int_buffer = np.int16(buffer * 32767)
            sound = pygame.sndarray.make_sound(int_buffer)
            loops = -1 if loop else 0
            channel = sound.play(loops=loops)
            voice.sound = sound
            voice.channel = channel
        if not self._enforce_voice_cap(bus_state, voice):
            return None
        bus_state.voices.append(voice)
        return voice

    def _enforce_voice_cap(self, bus_state: BusState, new_voice: Voice) -> bool:
        if len(bus_state.voices) < bus_state.cap:
            return True
        voices = bus_state.voices + [new_voice]
        voices.sort(key=lambda v: (-v.priority, -v.started_at))
        survivors = voices[: bus_state.cap]
        dropped = [v for v in voices if v not in survivors]
        for victim in dropped:
            if victim is new_voice:
                if victim.channel:
                    victim.channel.stop()
                _log(f"voice rejected bus={bus_state.name} event={victim.event}")
                return False
            if victim.channel:
                victim.channel.stop()
            if victim.loop:
                self._loops.pop(victim.event, None)
            if victim in bus_state.voices:
                bus_state.voices.remove(victim)
            _log(f"voice stolen bus={bus_state.name} victim={victim.event}")
        return True

    def _remove_voice(self, voice: Voice) -> None:
        bus_state = self._buses.get(voice.bus)
        if not bus_state:
            return
        if voice in bus_state.voices:
            bus_state.voices.remove(voice)

    def _cleanup_finished_voices(self) -> None:
        if not self.enable_audio or pygame is None:
            return
        for bus_state in self._buses.values():
            remaining = []
            for voice in bus_state.voices:
                channel = voice.channel
                if channel is not None and channel.get_busy():
                    remaining.append(voice)
                else:
                    if voice.loop and voice.event in self._loops:
                        self._loops.pop(voice.event, None)
            bus_state.voices = remaining
