"""In-memory renderer turning recipes into numpy buffers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict

import numpy as np

from ._logging import log_line
from .recipes import LayerSpec, RecipeSpec

SAMPLE_RATE = 48_000


@dataclass(frozen=True)
class RenderedSound:
    buffer: np.ndarray
    loop: bool
    loop_start: int
    loop_end: int


class Renderer:
    """Render recipes to stereo numpy buffers."""

    def __init__(self) -> None:
        self._cache: Dict[str, RenderedSound] = {}

    def render(self, recipe: RecipeSpec) -> RenderedSound:
        cached = self._cache.get(recipe.name)
        if cached is not None:
            return cached
        log_line("render", context="Renderer", data={"recipe": recipe.name})
        duration_samples = int(SAMPLE_RATE * (recipe.duration_ms / 1000.0))
        if duration_samples <= 0:
            duration_samples = 1
        mix = np.zeros(duration_samples, dtype=np.float32)
        for layer in recipe.layers:
            mix += self._render_layer(layer, duration_samples)
        peak = np.max(np.abs(mix)) or 1.0
        target = 10 ** (recipe.headroom_db / 20.0)
        mix = mix * (target / peak)
        stereo = np.stack([mix, mix], axis=1)
        loop_length = recipe.loop_length_ms or recipe.duration_ms
        loop_samples = min(int(SAMPLE_RATE * (loop_length / 1000.0)), len(mix))
        result = RenderedSound(buffer=stereo, loop=recipe.loop, loop_start=0, loop_end=loop_samples)
        self._cache[recipe.name] = result
        return result

    def _render_layer(self, layer: LayerSpec, sample_count: int) -> np.ndarray:
        rng = np.random.default_rng()
        start_offset = int(SAMPLE_RATE * (layer.randomize.start_ms / 1000.0))
        signal = np.zeros(sample_count, dtype=np.float32)
        if start_offset >= sample_count:
            return signal
        layer_len = sample_count - start_offset
        t = np.arange(layer_len, dtype=np.float32) / SAMPLE_RATE
        if layer.layer_type == "osc":
            freq = layer.freq_hz or 440.0
            freq = self._apply_pitch_random(freq, layer.randomize.pitch_semitones, rng)
            if layer.pitch_glide:
                start, end = layer.pitch_glide
                freq_curve = self._pitch_glide(freq, start, end, layer_len)
                phase = 2 * math.pi * np.cumsum(freq_curve) / SAMPLE_RATE
                wave = self._oscillator(phase, layer)
            else:
                phase = 2 * math.pi * freq * t
                wave = self._oscillator(phase, layer)
        else:  # noise
            wave = rng.uniform(-1.0, 1.0, layer_len).astype(np.float32)
            if layer.lp_hz:
                wave = self._low_pass(wave, layer.lp_hz)
        amp = layer.amp * self._amp_random(layer.randomize.amp_pct, rng)
        wave *= amp
        env = self._envelope_curve(layer.envelope, layer_len)
        segment = wave * env
        signal[start_offset:start_offset + layer_len] += segment
        return signal

    def _oscillator(self, phase: np.ndarray, layer: LayerSpec) -> np.ndarray:
        phase = np.asarray(phase, dtype=np.float32)
        if layer.layer_type != "osc":
            return np.zeros_like(phase)
        shape = getattr(layer, "wave", "sine")
        if shape == "square":
            return np.sign(np.sin(phase)).astype(np.float32)
        if shape == "triangle":
            return (2 / math.pi) * np.arcsin(np.sin(phase)).astype(np.float32)
        return np.sin(phase).astype(np.float32)

    def _pitch_glide(self, base_freq: float, start: float, end: float, total_length: int) -> np.ndarray:
        start_ratio = base_freq * (2 ** (start / 12.0))
        end_ratio = base_freq * (2 ** (end / 12.0))
        return np.linspace(start_ratio, end_ratio, total_length, dtype=np.float32)

    def _apply_pitch_random(self, freq: float, jitter: float, rng: np.random.Generator) -> float:
        if jitter == 0:
            return freq
        delta = rng.uniform(-jitter, jitter)
        return freq * (2 ** (delta / 12.0))

    def _amp_random(self, pct: float, rng: np.random.Generator) -> float:
        if pct == 0:
            return 1.0
        delta = rng.uniform(-pct, pct)
        return 1.0 + delta

    def _envelope_curve(self, env, total_length: int) -> np.ndarray:
        attack_samples = int(env.attack_ms * SAMPLE_RATE / 1000.0)
        decay_samples = int(env.decay_ms * SAMPLE_RATE / 1000.0)
        release_samples = int(env.release_ms * SAMPLE_RATE / 1000.0)
        sustain_level = env.sustain
        sustain_samples = max(0, total_length - attack_samples - decay_samples - release_samples)
        curve = np.zeros(total_length, dtype=np.float32)
        idx = 0
        if attack_samples > 0:
            curve[idx:idx+attack_samples] = np.linspace(0.0, 1.0, attack_samples, dtype=np.float32)
            idx += attack_samples
        if decay_samples > 0:
            curve[idx:idx+decay_samples] = np.linspace(1.0, sustain_level, decay_samples, dtype=np.float32)
            idx += decay_samples
        if sustain_samples > 0:
            curve[idx:idx+sustain_samples] = sustain_level
            idx += sustain_samples
        if release_samples > 0:
            start_level = curve[idx - 1] if idx > 0 else (sustain_level if sustain_samples > 0 else 1.0)
            curve[idx:idx+release_samples] = np.linspace(start_level, 0.0, release_samples, dtype=np.float32)
            idx += release_samples
        if idx < total_length:
            curve[idx:] = 0.0
        return curve

    def _low_pass(self, signal: np.ndarray, cutoff: float) -> np.ndarray:
        rc = 1.0 / (2 * math.pi * cutoff)
        dt = 1.0 / SAMPLE_RATE
        alpha = dt / (rc + dt)
        out = np.empty_like(signal)
        out[0] = alpha * signal[0]
        for i in range(1, len(signal)):
            out[i] = out[i - 1] + alpha * (signal[i] - out[i - 1])
        return out
