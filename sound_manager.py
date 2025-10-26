"""Procedural sound effects used across the game."""

from __future__ import annotations

import numpy as np
import pygame

from logger import log_debug


class SoundManager:
    """Generates and plays simple procedural sound effects."""

    def __init__(self) -> None:
        self.enabled = False
        self.sounds = {}
        self.loop_channels = {}

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.enabled = True
        except pygame.error as error:  # pragma: no cover - mixer failure path is tested
            log_debug("sound", f"mixer init failed: {error}")
            self.enabled = False

        if self.enabled:
            self._load_sounds()

    def _load_sounds(self) -> None:
        log_debug("sound", "loading sound bank")
        self.sounds = {
            "explosion": self._make_noise(0.4, 0.55),
            "player_fire": self._make_tone(920, 0.15, decay=4.0, volume=0.25),
            "special_activate": self._make_chord((660, 990, 1320), 0.35, volume=0.4),
            "pickup_refuel": self._make_chirp(520, 760, 0.25),
            "pickup_immunity": self._make_tone(660, 0.2, decay=3.5, volume=0.35),
            "pickup_tail_boost": self._make_tone(880, 0.18, decay=3.0, volume=0.3),
            "pickup_shield": self._make_chord((540, 810), 0.22, volume=0.32),
            "pickup_slow_motion": self._make_tone(420, 0.3, decay=2.0, volume=0.28),
            "pickup_score_multiplier": self._make_chord((700, 1050, 1400), 0.26, volume=0.35),
            "pickup_magnet": self._make_chirp(400, 950, 0.28),
            "pickup_score_boost": self._make_tone(990, 0.24, decay=3.2, volume=0.33),
            "pickup_special": self._make_chord((500, 750, 1000, 1250), 0.4, volume=0.38),
        }

    def _make_tone(self, frequency: float, duration: float, *, decay: float = 2.5, volume: float = 0.4):
        sample_rate = 44100
        times = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        envelope = np.exp(-decay * times)
        wave = (np.sin(2 * np.pi * frequency * times) * envelope * 32767).astype(np.int16)
        stereo = np.repeat(wave[:, np.newaxis], 2, axis=1)
        sound = pygame.sndarray.make_sound(stereo.copy())
        sound.set_volume(volume)
        return sound

    def _make_chord(self, frequencies, duration: float, *, volume: float = 0.4):
        sample_rate = 44100
        times = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        wave = np.zeros_like(times)
        for freq in frequencies:
            wave += np.sin(2 * np.pi * freq * times)
        wave = (wave / len(frequencies) * 32767).astype(np.int16)
        stereo = np.repeat(wave[:, np.newaxis], 2, axis=1)
        sound = pygame.sndarray.make_sound(stereo.copy())
        sound.set_volume(volume)
        return sound

    def _make_chirp(self, start_freq: float, end_freq: float, duration: float, *, volume: float = 0.35):
        sample_rate = 44100
        times = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        sweep = np.sin(2 * np.pi * (start_freq + (end_freq - start_freq) * times / duration) * times)
        wave = (sweep * np.exp(-2.0 * times) * 32767).astype(np.int16)
        stereo = np.repeat(wave[:, np.newaxis], 2, axis=1)
        sound = pygame.sndarray.make_sound(stereo.copy())
        sound.set_volume(volume)
        return sound

    def _make_noise(self, duration: float, volume: float):
        sample_rate = 44100
        samples = int(sample_rate * duration)
        noise = np.random.uniform(-1, 1, samples)
        envelope = np.linspace(1, 0, samples, endpoint=True)
        wave = (noise * envelope * 32767).astype(np.int16)
        stereo = np.repeat(wave[:, np.newaxis], 2, axis=1)
        sound = pygame.sndarray.make_sound(stereo.copy())
        sound.set_volume(volume)
        return sound

    def play(self, key: str) -> None:
        if not self.enabled:
            log_debug("sound", f"play skipped: {key}")
            return
        sound = self.sounds.get(key)
        if sound is None:
            log_debug("sound", f"missing sound: {key}")
            return
        log_debug("sound", f"play: {key}")
        sound.play()

    def loop(self, key: str) -> None:
        if not self.enabled:
            log_debug("sound", f"loop skipped: {key}")
            return
        if key in self.loop_channels:
            channel = self.loop_channels[key]
            if channel and channel.get_busy():
                return
        sound = self.sounds.get(key)
        if sound is None:
            log_debug("sound", f"missing loop sound: {key}")
            return
        log_debug("sound", f"loop start: {key}")
        channel = sound.play(loops=-1)
        if channel:
            self.loop_channels[key] = channel

    def stop(self, key: str) -> None:
        channel = self.loop_channels.pop(key, None)
        if channel:
            log_debug("sound", f"loop stop: {key}")
            channel.stop()
