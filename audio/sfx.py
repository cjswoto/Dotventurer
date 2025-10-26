"""Runtime SFX mixer and public API."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:  # pragma: no cover - pygame is optional in tests
    import pygame
except ModuleNotFoundError:  # pragma: no cover - headless environments
    pygame = None  # type: ignore

from .assets import AssetLibrary, AssetVariant
from .catalog import Catalog, EventSpec
from .logging_utils import log_line
from .proc_fallback import generate as generate_fallback

_DB_TO_LINEAR = math.log(10) / 20.0
_PITCH_BASE = 1.05946309436  # 12th root of 2


@dataclass
class Bus:
    name: str
    base_gain_db: float
    cap: int


@dataclass
class DuckWindow:
    gain_db: float
    remaining: float


@dataclass
class Voice:
    event: str
    bus: str
    priority: int
    start_time: float
    loop: bool
    left: float
    right: float
    channel: Optional["pygame.mixer.Channel"] = None
    virtual_time: float = 0.4


class SFX:
    """Mixer facade mirroring common middleware behaviours."""

    def __init__(self, enable_audio: bool = True, config_path: Optional[str] = None):
        log_line("SFX initialisation start")
        self.enable_audio = enable_audio and pygame is not None
        self.catalog = Catalog(config_path)
        self.asset_library = AssetLibrary(enable_audio=self.enable_audio)
        self.buses: Dict[str, Bus] = {
            "ui": Bus("ui", -10.0, 8),
            "sfx": Bus("sfx", -8.0, 16),
            "loops": Bus("loops", -14.0, 4),
            "music": Bus("music", -12.0, 2),
        }
        self._voices: Dict[str, List[Voice]] = {name: [] for name in self.buses}
        self._loops: Dict[str, Voice] = {}
        self._cooldowns: Dict[str, float] = {}
        self._variant_indices: Dict[str, int] = {}
        self._variant_cache: Dict[str, List[AssetVariant]] = {}
        self._fallback_cache: Dict[str, List[AssetVariant]] = {}
        self._ducking: Dict[str, List[DuckWindow]] = {name: [] for name in self.buses}
        self._duck_gain: Dict[str, float] = {name: 0.0 for name in self.buses}
        self._last_events: List[str] = []
        self._mixer_ready = False
        if self.enable_audio:
            self._initialise_mixer()
        log_line("SFX initialisation complete")

    # ------------------------------------------------------------------
    def _initialise_mixer(self) -> None:
        if pygame is None:
            self.enable_audio = False
            return
        total_channels = sum(bus.cap for bus in self.buses.values())
        try:
            pygame.mixer.init(frequency=48000, size=-16, channels=2)
            pygame.mixer.set_num_channels(total_channels)
            self._mixer_ready = True
            log_line(f"Mixer initialised with {total_channels} channels")
        except pygame.error as exc:  # pragma: no cover - runtime only
            log_line(f"Mixer initialisation failed: {exc}")
            self.enable_audio = False

    # ------------------------------------------------------------------
    def play(
        self, event: str, pos: Optional[tuple] = None, screen_size: Optional[tuple] = None
    ) -> bool:
        log_line(f"play({event}) invoked")
        spec = self.catalog.get(event)
        if spec.loop:
            return self.play_loop(event, pos=pos, screen_size=screen_size)
        if not self._cooldown_ready(spec):
            log_line(f"Cooldown active for {event}")
            return False
        voice = self._create_voice(spec, pos, screen_size, loop=False)
        if voice is None:
            return False
        if not self._register_voice(voice):
            log_line(f"Voice rejected (capacity/priorities) for {event}")
            return False
        self._start_channel(voice)
        self._arm_cooldown(spec)
        self._record_event(event)
        return True

    # ------------------------------------------------------------------
    def play_loop(
        self, event: str, pos: Optional[tuple] = None, screen_size: Optional[tuple] = None
    ) -> bool:
        log_line(f"play_loop({event}) invoked")
        spec = self.catalog.get(event)
        spec.loop = True
        existing = self._loops.get(event)
        voice = self._create_voice(spec, pos, screen_size, loop=True)
        if voice is None:
            return False
        if existing:
            existing.left = voice.left
            existing.right = voice.right
            existing.priority = voice.priority
            existing.virtual_time = float("inf")
            self._apply_voice_volume(existing)
            return True
        if not self._register_voice(voice):
            log_line(f"Loop rejected for {event}")
            return False
        channel = self._start_channel(voice)
        if channel is not None:
            voice.channel = channel
        voice.virtual_time = float("inf")
        self._loops[event] = voice
        self._record_event(event)
        return True

    # ------------------------------------------------------------------
    def stop_loop(self, event: str) -> bool:
        log_line(f"stop_loop({event}) invoked")
        voice = self._loops.pop(event, None)
        if not voice:
            return False
        self._remove_voice(voice)
        return True

    # ------------------------------------------------------------------
    def duck(self, bus: str, gain_db: float = -6.0, ms: int = 250) -> None:
        bus = bus.lower()
        log_line(f"duck({bus}, {gain_db} dB, {ms} ms)")
        if bus not in self._ducking:
            return
        window = DuckWindow(gain_db=gain_db, remaining=max(0.0, ms / 1000.0))
        self._ducking[bus].append(window)
        self._recalculate_duck(bus)

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        log_line(f"update({dt:.4f})")
        self._advance_cooldowns(dt)
        self._advance_ducking(dt)
        self._cull_finished_voices()
        self._refresh_loops()

    # ------------------------------------------------------------------
    def get_debug_snapshot(self) -> Dict[str, Dict[str, object]]:
        snapshot = {
            "buses": {
                name: {
                    "voices": len(voices),
                    "virtual": sum(1 for v in voices if v.channel is None),
                }
                for name, voices in self._voices.items()
            },
            "events": list(self._last_events[-10:]),
        }
        return snapshot

    # ------------------------------------------------------------------
    def _cooldown_ready(self, spec: EventSpec) -> bool:
        remaining = self._cooldowns.get(spec.name, 0.0)
        return remaining <= 0.0

    def _arm_cooldown(self, spec: EventSpec) -> None:
        self._cooldowns[spec.name] = max(0.0, spec.cooldown_ms / 1000.0)

    def _advance_cooldowns(self, dt: float) -> None:
        expired = []
        for event, remaining in self._cooldowns.items():
            remaining -= dt
            if remaining <= 0.0:
                expired.append(event)
            else:
                self._cooldowns[event] = remaining
        for event in expired:
            del self._cooldowns[event]

    # ------------------------------------------------------------------
    def _advance_ducking(self, dt: float) -> None:
        for bus, windows in self._ducking.items():
            active: List[DuckWindow] = []
            for window in windows:
                window.remaining -= dt
                if window.remaining > 0.0:
                    active.append(window)
            self._ducking[bus] = active
            self._recalculate_duck(bus)

    def _recalculate_duck(self, bus: str) -> None:
        if not self._ducking[bus]:
            self._duck_gain[bus] = 0.0
        else:
            self._duck_gain[bus] = min(window.gain_db for window in self._ducking[bus])
        log_line(f"Duck gain for {bus}: {self._duck_gain[bus]:.2f} dB")

    # ------------------------------------------------------------------
    def _create_voice(
        self, spec: EventSpec, pos: Optional[tuple], screen_size: Optional[tuple], loop: bool
    ) -> Optional[Voice]:
        variants = self._resolve_variants(spec)
        if not variants:
            log_line(f"No variants available for {spec.name}")
            return None
        variant_index = self._next_variant_index(spec.name, len(variants))
        variant = variants[variant_index]
        pitch = self._random_pitch(spec)
        volume_factor = self._random_volume(spec)
        left, right = self._compute_volumes(spec, volume_factor, pos, screen_size)
        voice = Voice(
            event=spec.name,
            bus=spec.bus if spec.bus in self.buses else "sfx",
            priority=spec.priority,
            start_time=time.time(),
            loop=loop,
            left=left,
            right=right,
        )
        sound = self.asset_library.build_sound(variant, pitch)
        if sound is not None:
            voice.channel = self._prepare_channel(sound, loop)
        elif self.enable_audio and variant.path.name.endswith(".proc"):
            # Already handled by build_sound when audio disabled
            pass
        return voice

    # ------------------------------------------------------------------
    def _prepare_channel(self, sound, loop: bool):
        if not self.enable_audio or not self._mixer_ready or pygame is None:
            return None
        channel = pygame.mixer.find_channel()
        if channel is None:
            log_line("No free channel available; voice virtualised")
            return None
        channel.set_volume(0.0, 0.0)
        channel.play(sound, loops=-1 if loop else 0)
        return channel

    def _start_channel(self, voice: Voice) -> Optional["pygame.mixer.Channel"]:
        if voice.channel is None or not self.enable_audio:
            return None
        voice.channel.set_volume(voice.left, voice.right)
        return voice.channel

    # ------------------------------------------------------------------
    def _register_voice(self, voice: Voice) -> bool:
        bus_name = voice.bus
        voices = self._voices[bus_name]
        if len(voices) >= self.buses[bus_name].cap:
            victim = self._choose_voice_to_steal(voices, voice.priority)
            if victim is None:
                return False
            self._remove_voice(victim)
        voices.append(voice)
        return True

    def _remove_voice(self, voice: Voice) -> None:
        bus_voices = self._voices.get(voice.bus)
        if bus_voices and voice in bus_voices:
            bus_voices.remove(voice)
        if voice.channel is not None and self.enable_audio:
            voice.channel.stop()
        if voice.event in self._loops and self._loops[voice.event] is voice:
            del self._loops[voice.event]

    def _choose_voice_to_steal(self, voices: List[Voice], incoming_priority: int) -> Optional[Voice]:
        ordered = sorted(voices, key=lambda v: (v.priority, v.start_time))
        for candidate in ordered:
            if candidate.priority <= incoming_priority:
                return candidate
        return None

    # ------------------------------------------------------------------
    def _resolve_variants(self, spec: EventSpec) -> List[AssetVariant]:
        if spec.name in self._variant_cache:
            return self._variant_cache[spec.name]
        variants = self.asset_library.variants_for(spec.name, spec.variants)
        if not variants:
            variants = self._fallback_variants(spec.name)
        self._variant_cache[spec.name] = variants
        return variants

    def _fallback_variants(self, event: str) -> List[AssetVariant]:
        if event not in self._fallback_cache:
            generated: List[AssetVariant] = []
            for idx in range(3):
                seed = (hash(event) + idx) & 0xFFFF
                fallback = generate_fallback(seed=seed)
                path = Path(f"{event}_fallback_{idx}.proc")
                generated.append(
                    AssetVariant(event=event, path=path, samples=fallback.samples, sample_rate=fallback.sample_rate)
                )
            self._fallback_cache[event] = generated
        return self._fallback_cache[event]

    # ------------------------------------------------------------------
    def _next_variant_index(self, event: str, total: int) -> int:
        idx = self._variant_indices.get(event, 0)
        self._variant_indices[event] = (idx + 1) % total
        return idx

    def _random_pitch(self, spec: EventSpec) -> float:
        spread = spec.pitch_jitter_semitones
        if spread <= 0:
            return 1.0
        semitones = random.uniform(-spread, spread)
        return _PITCH_BASE ** semitones

    def _random_volume(self, spec: EventSpec) -> float:
        spread = spec.vol_jitter
        if spread <= 0:
            return 1.0
        return random.uniform(max(0.0, 1.0 - spread), 1.0 + spread)

    def _compute_volumes(
        self, spec: EventSpec, volume_factor: float, pos: Optional[tuple], screen_size: Optional[tuple]
    ) -> Tuple[float, float]:
        bus = self.buses.get(spec.bus, self.buses["sfx"])
        total_db = bus.base_gain_db + spec.base_gain + self._duck_gain.get(bus.name, 0.0)
        linear_gain = math.exp(total_db * _DB_TO_LINEAR) * volume_factor
        if not spec.pan or pos is None or screen_size is None:
            return linear_gain, linear_gain
        x = float(pos[0])
        width = float(screen_size[0])
        if width <= 0:
            return linear_gain, linear_gain
        normalised = max(-1.0, min(1.0, (x / width) * 2.0 - 1.0))
        left = math.sqrt((1.0 - normalised) / 2.0)
        right = math.sqrt((1.0 + normalised) / 2.0)
        # Constant-power pan ensures centre stays level with edges.
        return linear_gain * left, linear_gain * right

    # ------------------------------------------------------------------
    def _cull_finished_voices(self) -> None:
        for bus, voices in self._voices.items():
            remaining: List[Voice] = []
            for voice in voices:
                if voice.loop:
                    remaining.append(voice)
                    continue
                if voice.channel is not None and self.enable_audio:
                    if voice.channel.get_busy():
                        remaining.append(voice)
                        continue
                voice.virtual_time -= 0.016
                if voice.virtual_time > 0:
                    remaining.append(voice)
            self._voices[bus] = remaining

    def _refresh_loops(self) -> None:
        for voice in list(self._loops.values()):
            self._apply_voice_volume(voice)

    def _apply_voice_volume(self, voice: Voice) -> None:
        if voice.channel is not None and self.enable_audio:
            voice.channel.set_volume(voice.left, voice.right)

    def _record_event(self, event: str) -> None:
        self._last_events.append(event)
        if len(self._last_events) > 10:
            self._last_events = self._last_events[-10:]

