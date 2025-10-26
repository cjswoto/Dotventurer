"""Procedural sound generation and playback helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pygame

from logging_utils import log_debug


@dataclass(frozen=True)
class SoundSpec:
    """Configuration for a procedurally generated sound."""

    frequency: int
    duration: float
    volume: float
    waveform: str = "sine"


class SoundManager:
    """Generate and play custom sounds for game events."""

    SAMPLE_RATE = 44_100

    def __init__(self, enable_audio: bool = True) -> None:
        self.sound_specs: Dict[str, SoundSpec] = {
            "explosion": SoundSpec(frequency=0, duration=0.6, volume=0.6, waveform="noise"),
            "pickup_refuel": SoundSpec(frequency=420, duration=0.25, volume=0.5),
            "pickup_immunity": SoundSpec(frequency=520, duration=0.25, volume=0.55),
            "pickup_tail_boost": SoundSpec(frequency=640, duration=0.25, volume=0.6),
            "pickup_shield": SoundSpec(frequency=760, duration=0.25, volume=0.55),
            "pickup_slow_motion": SoundSpec(frequency=340, duration=0.3, volume=0.5),
            "pickup_score_multiplier": SoundSpec(frequency=880, duration=0.3, volume=0.6),
            "pickup_magnet": SoundSpec(frequency=980, duration=0.3, volume=0.55),
            "pickup_score_boost": SoundSpec(frequency=440, duration=0.2, volume=0.5),
            "pickup_special": SoundSpec(frequency=1_020, duration=0.35, volume=0.65),
            "player_attack": SoundSpec(frequency=700, duration=0.15, volume=0.45, waveform="triangle"),
            "player_attack_hit": SoundSpec(frequency=1_200, duration=0.1, volume=0.5),
            "special_activate": SoundSpec(frequency=300, duration=0.8, volume=0.6),
        }
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        self._loop_channels: Dict[str, Optional[pygame.mixer.Channel]] = {}
        self.enabled = False

        if enable_audio:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.set_num_channels(max(8, len(self.sound_specs)))
                self.enabled = True
            except pygame.error as exc:
                log_debug(f"SoundManager mixer init failed: {exc}")
                self.enabled = False
        if self.enabled:
            log_debug("SoundManager initialising procedural sounds")
            self._prepare_sounds()
        else:
            log_debug("SoundManager running without audio output")

    def _prepare_sounds(self) -> None:
        for key, spec in self.sound_specs.items():
            try:
                self.sounds[key] = self._create_sound(spec)
                log_debug(f"Prepared sound '{key}' with spec {spec}")
            except RuntimeError as exc:
                log_debug(f"Failed to prepare sound '{key}': {exc}")
                self.enabled = False
                self.sounds.clear()
                self._loop_channels.clear()
                break

    def _create_sound(self, spec: SoundSpec) -> pygame.mixer.Sound:
        sample_count = max(1, int(self.SAMPLE_RATE * spec.duration))
        if spec.waveform == "noise":
            wave = np.random.uniform(-1.0, 1.0, sample_count)
        else:
            times = np.linspace(0, spec.duration, sample_count, endpoint=False, dtype=np.float32)
            if spec.waveform == "triangle":
                cycle = (times * spec.frequency) % 1
                wave = 4 * np.abs(cycle - 0.5) - 1
            else:
                wave = np.sin(2 * np.pi * spec.frequency * times)
        audio = np.stack((wave, wave), axis=1)
        int_audio = (audio * 32_767).astype(np.int16)
        try:
            from pygame import sndarray
        except ImportError as exc:
            raise RuntimeError("pygame.sndarray unavailable") from exc
        sound = sndarray.make_sound(int_audio)
        sound.set_volume(spec.volume)
        return sound

    def play(self, key: str) -> None:
        if not self.enabled:
            log_debug(f"Skipped playing '{key}' (audio disabled)")
            return
        sound = self.sounds.get(key)
        if sound is None:
            log_debug(f"Sound '{key}' not found")
            return
        sound.play()
        log_debug(f"Played sound '{key}' once")

    def play_loop(self, key: str) -> None:
        if not self.enabled:
            log_debug(f"Skipped loop play for '{key}' (audio disabled)")
            return
        if key in self._loop_channels:
            channel = self._loop_channels[key]
            if channel is not None and channel.get_busy():
                return
        sound = self.sounds.get(key)
        if sound is None:
            log_debug(f"Loop sound '{key}' not found")
            return
        channel = sound.play(loops=-1)
        self._loop_channels[key] = channel
        log_debug(f"Started loop for '{key}'")

    def stop_loop(self, key: str) -> None:
        if not self.enabled:
            return
        channel = self._loop_channels.pop(key, None)
        if channel is not None:
            channel.stop()
            log_debug(f"Stopped loop for '{key}'")

    def stop_all(self) -> None:
        if not self.enabled:
            return
        for key, channel in list(self._loop_channels.items()):
            if channel is not None:
                channel.stop()
                log_debug(f"Stopped loop for '{key}' via stop_all")
        self._loop_channels.clear()
