"""Centralised sound manager for contextual audio cues."""

from __future__ import annotations

import math
from typing import Dict

import numpy as np
import pygame

from config import LOG_ENABLED
from logging_utils import log_debug


class SoundManager:
    """Load and trigger short procedural sounds for game events."""

    def __init__(self) -> None:
        if LOG_ENABLED:
            log_debug("SoundManager.__init__")
        self.sounds: Dict[str, pygame.mixer.Sound | None] = {}
        self.available = self._init_mixer()
        self._load_sounds()

    def _init_mixer(self) -> bool:
        mixer = getattr(pygame, "mixer", None)
        if mixer is None:
            if LOG_ENABLED:
                log_debug("SoundManager mixer unavailable: attribute missing")
            return False
        try:
            if not mixer.get_init():
                mixer.init()
            if LOG_ENABLED:
                log_debug("SoundManager mixer ready")
            return True
        except Exception as exc:
            if LOG_ENABLED:
                log_debug(f"SoundManager mixer unavailable: {exc}")
            return False

    def _load_sounds(self) -> None:
        base_freq = 330
        mapping = {
            "default": base_freq,
            "explosion": base_freq * 1.5,
            "special_activation": base_freq * 1.8,
            "attack_hit": base_freq * 2.2,
            "trail_hit": base_freq * 1.9,
            "pickup_powerup": base_freq * 1.1,
            "pickup_immunity": base_freq * 1.2,
            "pickup_tail_boost": base_freq * 1.3,
            "pickup_shield": base_freq * 1.4,
            "pickup_slow_motion": base_freq * 0.9,
            "pickup_score_multiplier": base_freq * 2.0,
            "pickup_magnet": base_freq * 1.6,
            "pickup_ScoreBoostPickup": base_freq * 2.4,
            "pickup_SpecialPickup": base_freq * 2.6,
        }
        for key, frequency in mapping.items():
            self.sounds[key] = self._create_tone(frequency) if self.available else None
            if LOG_ENABLED:
                log_debug(f"Loaded sound {key} available={self.available}")

    def _create_tone(self, frequency: float, duration: float = 0.25) -> pygame.mixer.Sound | None:
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        wave = 0.3 * np.sin(2 * math.pi * frequency * t)
        samples = np.int16(np.column_stack((wave, wave)) * 32767)
        sndarray = getattr(pygame, "sndarray", None)
        if sndarray is None or not hasattr(sndarray, "make_sound"):
            if LOG_ENABLED:
                log_debug("SoundManager missing sndarray.make_sound")
            return None
        return sndarray.make_sound(samples)

    def play(self, event: str) -> None:
        clip = self.sounds.get(event) or self.sounds.get("default")
        if LOG_ENABLED:
            log_debug(
                f"SoundManager.play event={event} available={self.available} clip={'yes' if clip else 'no'}"
            )
        if not self.available or clip is None:
            return
        clip.play()

    def _pickup_key(self, pickup: object) -> str:
        effect = getattr(pickup, "effect", None)
        if effect:
            return f"pickup_{effect}"
        return f"pickup_{pickup.__class__.__name__}"

    def play_for_pickup(self, pickup: object) -> None:
        event = self._pickup_key(pickup)
        if event not in self.sounds:
            event = "pickup_powerup"
        if LOG_ENABLED:
            log_debug(f"SoundManager.play_for_pickup event={event}")
        self.play(event)


sound_manager = SoundManager()
