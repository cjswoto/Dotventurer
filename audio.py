"""Audio utilities for procedural music and effects."""

import os
import time
from typing import Dict

import numpy as np
import pygame

from config import LOG_ENABLED, LOG_FILE_PATH, settings_data


SAMPLE_RATE = 44100


def _log(message: str) -> None:
    if not LOG_ENABLED:
        return
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(f"{timestamp} audio: {message}\n")


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


class AudioManager:
    """Handles procedural audio playback for music and effects."""

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        if LOG_ENABLED:
            _log("AudioManager.__init__ start")
        self.sample_rate = sample_rate
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=self.sample_rate, size=-16, channels=2)
        else:
            current_rate = pygame.mixer.get_init()[0]
            if current_rate != self.sample_rate:
                pygame.mixer.quit()
                pygame.mixer.init(frequency=self.sample_rate, size=-16, channels=2)

        pygame.mixer.set_num_channels(max(pygame.mixer.get_num_channels(), 4))
        self.music_channel = pygame.mixer.Channel(0)
        self.effects_channel = pygame.mixer.Channel(1)

        self.music_sound = self._create_music_sound()
        self.sfx_sounds = self._create_effect_sounds()
        self.apply_settings()
        if LOG_ENABLED:
            _log("AudioManager.__init__ complete")

    def play_music(self) -> None:
        if LOG_ENABLED:
            _log("AudioManager.play_music invoked")
        if not self.music_channel.get_busy():
            self.music_channel.play(self.music_sound, loops=-1)

    def play_effect(self, name: str) -> None:
        if LOG_ENABLED:
            _log(f"AudioManager.play_effect {name}")
        sound = self.sfx_sounds.get(name)
        if sound is None:
            return
        self.effects_channel.play(sound)

    def apply_settings(self) -> None:
        if LOG_ENABLED:
            _log("AudioManager.apply_settings start")
        music_volume = _clamp(float(settings_data.get("MUSIC_VOLUME", 0.6)), 0.0, 1.0)
        sfx_volume = _clamp(float(settings_data.get("SFX_VOLUME", 0.7)), 0.0, 1.0)
        self.music_sound.set_volume(music_volume)
        self.music_channel.set_volume(music_volume)
        for sound in self.sfx_sounds.values():
            sound.set_volume(sfx_volume)
        self.effects_channel.set_volume(sfx_volume)
        if LOG_ENABLED:
            _log("AudioManager.apply_settings complete")

    def _create_music_sound(self) -> pygame.mixer.Sound:
        if LOG_ENABLED:
            _log("AudioManager._create_music_sound")
        beat_duration = 0.5
        t = np.linspace(0, beat_duration, int(self.sample_rate * beat_duration), False)
        chord = (
            np.sin(2 * np.pi * 220 * t)
            + 0.6 * np.sin(2 * np.pi * 440 * t)
            + 0.4 * np.sin(2 * np.pi * 330 * t)
        )
        chord *= np.linspace(0.8, 0.4, chord.size)
        arpeggio = np.concatenate([
            np.sin(2 * np.pi * freq * t) * np.linspace(0.2, 0.05, t.size)
            for freq in (660, 550, 440, 330)
        ])
        music_wave = np.tile(np.concatenate([chord, arpeggio]), 4)
        music_wave = np.clip(music_wave / np.max(np.abs(music_wave)), -1.0, 1.0)
        return self._to_sound(music_wave)

    def _create_effect_sounds(self) -> Dict[str, pygame.mixer.Sound]:
        if LOG_ENABLED:
            _log("AudioManager._create_effect_sounds")
        return {
            "explosion": self._create_explosion_sound(),
            "pickup": self._create_pickup_sound(),
            "special": self._create_special_sound(),
        }

    def _create_explosion_sound(self) -> pygame.mixer.Sound:
        duration = 0.5
        t = np.linspace(0, duration, int(self.sample_rate * duration), False)
        noise = np.random.uniform(-1, 1, t.size)
        envelope = np.linspace(1.0, 0.0, t.size) ** 2
        wave = noise * envelope
        return self._to_sound(wave)

    def _create_pickup_sound(self) -> pygame.mixer.Sound:
        duration = 0.25
        t = np.linspace(0, duration, int(self.sample_rate * duration), False)
        sweep = np.sin(2 * np.pi * (440 + 440 * t**2) * t)
        envelope = np.linspace(0.2, 0.0, t.size)
        wave = sweep * envelope
        return self._to_sound(wave)

    def _create_special_sound(self) -> pygame.mixer.Sound:
        duration = 0.4
        t = np.linspace(0, duration, int(self.sample_rate * duration), False)
        base = np.sin(2 * np.pi * 110 * t)
        harmony = np.sin(2 * np.pi * 330 * t) * np.linspace(0.3, 0.0, t.size)
        wave = base * np.linspace(0.4, 0.0, t.size) + harmony
        return self._to_sound(wave)

    def _to_sound(self, wave: np.ndarray) -> pygame.mixer.Sound:
        stereo = np.column_stack((wave, wave))
        stereo = np.clip(stereo, -1.0, 1.0)
        int_wave = np.int16(stereo * 32767)
        return pygame.sndarray.make_sound(int_wave.copy())
