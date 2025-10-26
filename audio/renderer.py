"""Renderer for procedural sound recipes."""
from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import Dict

import numpy as np

from config import AUDIO_LOG_ENABLED
from .recipes import LayerSpec, RecipeLibrary, RecipeSpec

SAMPLE_RATE = 48_000
TWO_PI = 2 * math.pi


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _log(message: str) -> None:
    if not AUDIO_LOG_ENABLED:
        return
    os.makedirs("logs", exist_ok=True)
    with open("logs/debug.txt", "a", encoding="utf-8") as handle:
        handle.write(f"[{_timestamp()}][renderer] {message}\n")


def semitone_ratio(offset: float) -> float:
    """Convert a semitone offset into a playback ratio."""
    return 2.0 ** (offset / 12.0)


@dataclass
class RenderResult:
    buffer: np.ndarray  # stereo float32 in range [-1, 1]
    sample_rate: int = SAMPLE_RATE


class RecipeRenderer:
    """Render RecipeSpec instances into ready-to-play buffers."""

    def __init__(self, library: RecipeLibrary):
        self.library = library
        self._cache: Dict[str, RenderResult] = {}

    def render(self, recipe_id: str) -> RenderResult:
        if recipe_id not in self._cache:
            spec = self.library.get(recipe_id)
            _log(f"render {recipe_id}")
            self._cache[recipe_id] = self._render_spec(spec)
        return self._cache[recipe_id]

    def _render_spec(self, spec: RecipeSpec) -> RenderResult:
        duration_s = spec.duration_ms / 1000.0
        total_samples = int(SAMPLE_RATE * duration_s)
        mix = np.zeros(total_samples, dtype=np.float32)
        rng = np.random.default_rng()

        for idx, layer in enumerate(spec.layers):
            _log(f"layer {spec.recipe_id}#{idx} type={layer.layer_type}")
            layer_signal = self._render_layer(layer, total_samples, rng)
            mix[: len(layer_signal)] += layer_signal

        peak = float(np.max(np.abs(mix))) if mix.size else 0.0
        target_peak = 10 ** (spec.headroom_db / 20.0)
        if peak > 0:
            mix *= target_peak / peak
        stereo = np.stack([mix, mix], axis=1)
        return RenderResult(buffer=stereo)

    def _render_layer(
        self,
        layer: LayerSpec,
        total_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        signal = np.zeros(total_samples, dtype=np.float32)
        amp = layer.amp
        randomize = layer.randomize or {}
        if randomize:
            amp *= 1 + rng.uniform(-1, 1) * (randomize.get("amp_pct", 0.0) / 100.0)
        env = self._envelope(layer.env, total_samples)
        start_shift = 0
        if "start_ms" in randomize:
            jitter = float(randomize.get("start_ms", 0.0))
            start_shift = int(SAMPLE_RATE * (rng.uniform(-jitter, jitter) / 1000.0))
        if layer.layer_type == "noise":
            signal = rng.uniform(-1.0, 1.0, total_samples).astype(np.float32)
            cutoff = layer.lp_hz or 12000.0
            signal = self._low_pass(signal, cutoff)
        else:
            freq = layer.freq_hz or 440.0
            pitch_rand = randomize.get("pitch_semitones")
            if pitch_rand is not None:
                freq *= semitone_ratio(rng.uniform(-pitch_rand, pitch_rand))
            glide = layer.glide or {}
            start = glide.get("start_semitones", 0.0)
            end = glide.get("end_semitones", 0.0)
            pitch_curve = np.linspace(start, end, total_samples, dtype=np.float32)
            ratios = np.vectorize(semitone_ratio)(pitch_curve)
            phase = np.cumsum(freq * ratios / SAMPLE_RATE)
            raw = self._oscillator(layer.layer_type, phase)
            signal = raw
            if layer.lp_hz:
                signal = self._low_pass(signal, layer.lp_hz)
        signal = signal * env * amp
        if start_shift != 0:
            signal = self._shift(signal, start_shift)
        return signal

    def _envelope(self, env: Dict[str, float], total_samples: int) -> np.ndarray:
        attack = int(SAMPLE_RATE * (env.get("attack_ms", 0.0) / 1000.0))
        decay = int(SAMPLE_RATE * (env.get("decay_ms", 0.0) / 1000.0))
        release = int(SAMPLE_RATE * (env.get("release_ms", 0.0) / 1000.0))
        sustain = float(env.get("sustain", 1.0))
        sustain_samples = max(total_samples - (attack + decay + release), 0)

        curve = np.zeros(total_samples, dtype=np.float32)
        cursor = 0
        if attack > 0:
            curve[:attack] = np.linspace(0.0, 1.0, attack, dtype=np.float32)
            cursor += attack
        if decay > 0:
            curve[cursor : cursor + decay] = np.linspace(1.0, sustain, decay, dtype=np.float32)
            cursor += decay
        if sustain_samples > 0:
            curve[cursor : cursor + sustain_samples] = sustain
            cursor += sustain_samples
        if release > 0 and cursor < total_samples:
            start_val = curve[cursor - 1] if cursor > 0 else sustain
            curve[cursor:total_samples] = np.linspace(start_val, 0.0, total_samples - cursor, dtype=np.float32)
        else:
            curve[cursor:total_samples] = 0.0
        return curve

    def _oscillator(self, osc_type: str, phase: np.ndarray) -> np.ndarray:
        phase = np.mod(phase, 1.0)
        if osc_type == "sine":
            return np.sin(phase * TWO_PI, dtype=np.float32)
        if osc_type == "triangle":
            return (2 * np.abs(2 * (phase - np.floor(phase + 0.5))) - 1).astype(np.float32)
        if osc_type == "square":
            return np.where(phase < 0.5, 1.0, -1.0).astype(np.float32)
        return np.sin(phase * TWO_PI, dtype=np.float32)

    def _low_pass(self, signal: np.ndarray, cutoff_hz: float) -> np.ndarray:
        if cutoff_hz <= 0:
            return np.zeros_like(signal)
        rc = 1.0 / (cutoff_hz * TWO_PI)
        dt = 1.0 / SAMPLE_RATE
        alpha = dt / (rc + dt)
        filtered = np.empty_like(signal)
        filtered[0] = signal[0]
        for i in range(1, signal.size):
            filtered[i] = filtered[i - 1] + alpha * (signal[i] - filtered[i - 1])
        return filtered

    def _shift(self, signal: np.ndarray, offset: int) -> np.ndarray:
        if offset == 0:
            return signal
        shifted = np.zeros_like(signal)
        if offset > 0:
            shifted[offset:] = signal[:-offset]
        else:
            shifted[:offset] = signal[-offset:]
        return shifted


def render_recipe(library: RecipeLibrary, recipe_id: str) -> RenderResult:
    return RecipeRenderer(library).render(recipe_id)
