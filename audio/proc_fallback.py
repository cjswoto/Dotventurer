"""Procedural fallback tone generation for missing assets."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .logging_utils import log_line

_SAMPLE_RATE = 48000
_ATTACK_MS = 8
_RELEASE_MS = 45
_PEAK_LEVEL = 0.5  # ~-6 dBFS when converted to 16-bit PCM


@dataclass
class FallbackSound:
    """Container for generated fallback samples."""

    samples: np.ndarray
    sample_rate: int = _SAMPLE_RATE


def generate(duration_ms: int = 160, seed: int = 0) -> FallbackSound:
    """Generate a short, smooth noise burst to avoid silence."""

    log_line(f"Generating fallback asset: {duration_ms} ms seed={seed}")
    total_samples = max(1, int(_SAMPLE_RATE * duration_ms / 1000))
    base = np.random.default_rng(seed).normal(0.0, 1.0, total_samples)
    base = _tilt(base)
    envelope = _envelope(total_samples)
    samples = (base * envelope * _PEAK_LEVEL).astype(np.float32)
    return FallbackSound(samples=samples.reshape(-1, 1))


def _envelope(length: int) -> np.ndarray:
    attack = int(_SAMPLE_RATE * _ATTACK_MS / 1000)
    release = int(_SAMPLE_RATE * _RELEASE_MS / 1000)
    sustain = max(0, length - attack - release)
    env = np.ones(length, dtype=np.float32)
    if attack:
        env[:attack] = np.linspace(0.0, 1.0, attack, endpoint=False)
    if release:
        env[-release:] = np.linspace(1.0, 0.0, release, endpoint=False)
    if sustain:
        env[attack : attack + sustain] = 1.0
    return env


def _tilt(signal: np.ndarray) -> np.ndarray:
    fft = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(signal.size, d=1.0 / _SAMPLE_RATE)
    tilt = np.clip(1.0 / np.sqrt(freqs + 1.0), 0.2, 1.0)
    fft *= tilt
    return np.fft.irfft(fft, n=signal.size)
