"""Sound management utilities for Dotventurer."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pygame

from log_utils import log_debug


SAMPLE_RATE = 44100


class DummySound:
    """Fallback sound object when the mixer is unavailable."""

    def play(self, *args, **kwargs):
        return None

    def stop(self):
        return None


class SoundLibrary:
    """Small library of generated sounds keyed by gameplay events."""

    def __init__(self) -> None:
        self._mixer_ready = False
        self.sounds: dict[str, DummySound | pygame.mixer.Sound] = {}
        self._init_mixer()
        self._build_library()

    def play(self, name: str) -> None:
        sound = self.sounds.get(name)
        if not sound:
            return
        log_debug(f"SoundLibrary.play name={name}")
        try:
            sound.play()
        except TypeError:
            sound.play(loops=0)

    def loop(self, name: str) -> None:
        sound = self.sounds.get(name)
        if not sound:
            return
        log_debug(f"SoundLibrary.loop name={name}")
        try:
            sound.play(loops=-1)
        except TypeError:
            sound.play()

    def stop(self, name: str) -> None:
        sound = self.sounds.get(name)
        if not sound:
            return
        log_debug(f"SoundLibrary.stop name={name}")
        if hasattr(sound, "stop"):
            sound.stop()

    def _init_mixer(self) -> None:
        mixer = getattr(pygame, "mixer", None)
        get_init = getattr(mixer, "get_init", None)
        if not callable(get_init):
            log_debug("SoundLibrary._init_mixer skipped (no mixer)")
            return
        try:
            if not mixer.get_init():
                mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1)
            self._mixer_ready = True
            log_debug("SoundLibrary._init_mixer ready")
        except (pygame.error, TypeError, ValueError):
            self._mixer_ready = False
            log_debug("SoundLibrary._init_mixer failed")

    def _build_library(self) -> None:
        log_debug("SoundLibrary._build_library start")
        self._register("explosion", (110, 220, 65), 0.3, 0.35)
        self._register("special_activate", (440, 660, 880), 0.4, 0.45)
        self._register("attack_emit", (280, 360), 0.25, 0.5)
        self._register("attack_hit", (520,), 0.35, 0.2)

        self._register("pickup_powerup", (523, 784), 0.3, 0.25)
        self._register("pickup_immunity", (392, 523, 659), 0.3, 0.3)
        self._register("pickup_tail_boost", (659, 880), 0.3, 0.25)
        self._register("pickup_shield", (262, 349, 523), 0.3, 0.25)
        self._register("pickup_slow_motion", (196, 247), 0.25, 0.35)
        self._register("pickup_score_multiplier", (523, 659, 784), 0.35, 0.25)
        self._register("pickup_magnet", (330, 494, 698), 0.3, 0.3)
        self._register("pickup_score_boost", (784, 988), 0.35, 0.2)
        self._register("pickup_special", (440, 554, 659, 880), 0.4, 0.3)
        log_debug("SoundLibrary._build_library complete")

    def _register(self, name: str, tones: Iterable[float], volume: float, duration: float) -> None:
        log_debug(f"SoundLibrary._register name={name}")
        self.sounds[name] = self._create_tone(tones, volume, duration)

    def _create_tone(self, tones: Iterable[float], volume: float, duration: float):
        if not self._mixer_ready or not hasattr(pygame, "sndarray"):
            log_debug("SoundLibrary._create_tone fallback dummy")
            return DummySound()
        make_sound = getattr(pygame.sndarray, "make_sound", None)
        if not callable(make_sound):
            log_debug("SoundLibrary._create_tone missing make_sound")
            return DummySound()
        samples = max(1, int(SAMPLE_RATE * duration))
        timeline = np.linspace(0, duration, samples, False)
        waveform = np.zeros_like(timeline)
        tones_list = list(tones)
        for freq in tones_list:
            waveform += np.sin(2 * math.pi * freq * timeline)
        waveform /= max(1, len(tones_list))
        waveform *= volume
        audio = np.int16(np.clip(waveform, -1.0, 1.0) * 32767)
        try:
            log_debug("SoundLibrary._create_tone generated")
            return make_sound(audio)
        except (pygame.error, TypeError, ValueError):
            log_debug("SoundLibrary._create_tone generation failed")
            return DummySound()
