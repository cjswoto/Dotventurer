"""Procedural audio renderer that outputs stereo NumPy buffers."""

from __future__ import annotations

import math
import random

import numpy as np

from .recipes import LayerSpec, RecipeLibrary, RecipeSpec
from .utils import SAMPLE_RATE, db_to_gain, log_debug


def _equal_tempered_ratio(semitones: float) -> float:
    return 2 ** (semitones / 12.0)


def _render_envelope(envelope, total_samples: int) -> np.ndarray:
    attack = max(1, int(envelope.attack_ms / 1000.0 * SAMPLE_RATE))
    decay = max(1, int(envelope.decay_ms / 1000.0 * SAMPLE_RATE))
    release = max(1, int(envelope.release_ms / 1000.0 * SAMPLE_RATE))
    sustain_samples = max(0, total_samples - attack - decay - release)

    attack_curve = np.linspace(0.0, 1.0, attack, endpoint=False)
    decay_curve = np.linspace(1.0, envelope.sustain, decay, endpoint=False)
    sustain_curve = np.full(sustain_samples, envelope.sustain)
    release_curve = np.linspace(envelope.sustain, 0.0, release, endpoint=True)
    envelope_curve = np.concatenate((attack_curve, decay_curve, sustain_curve, release_curve))
    if envelope_curve.size < total_samples:
        pad = np.zeros(total_samples - envelope_curve.size)
        envelope_curve = np.concatenate((envelope_curve, pad))
    return envelope_curve[:total_samples]


class Renderer:
    """Render ``RecipeSpec`` definitions to stereo floating-point buffers."""

    def __init__(self, library: RecipeLibrary) -> None:
        self._library = library
    def render(self, recipe_id: str, pitch_semitones: float = 0.0, amp_multiplier: float = 1.0) -> np.ndarray:
        """Render ``recipe_id`` into a stereo buffer with jitter applied."""

        recipe = self._library.get(recipe_id)
        log_debug(f"renderer:render recipe={recipe_id} pitch={pitch_semitones:.3f} amp={amp_multiplier:.3f}")
        mono = self._render_recipe(recipe, pitch_semitones)
        target_peak = db_to_gain(recipe.headroom_db)
        peak = np.max(np.abs(mono)) or 1.0
        mono = mono * (target_peak / peak) * amp_multiplier
        stereo = np.column_stack((mono, mono)).astype(np.float32)
        return stereo

    def _render_recipe(self, recipe: RecipeSpec, pitch_semitones: float) -> np.ndarray:
        total_samples = int(SAMPLE_RATE * recipe.duration_ms / 1000.0)
        buffer = np.zeros(total_samples, dtype=np.float32)
        for layer in recipe.layers:
            layer_buffer = self._render_layer(layer, total_samples, pitch_semitones)
            buffer[: layer_buffer.size] += layer_buffer
        return buffer

    def _render_layer(self, layer: LayerSpec, total_samples: int, event_pitch: float) -> np.ndarray:
        jitter = random.uniform(-layer.randomize.start_ms, layer.randomize.start_ms)
        start_ms = max(0.0, layer.start_ms + jitter)
        start_offset = int(start_ms / 1000.0 * SAMPLE_RATE)
        layer_samples = total_samples - start_offset
        if layer_samples <= 0:
            return np.zeros(0, dtype=np.float32)
        layer_pitch = event_pitch + random.uniform(-layer.randomize.pitch_semitones, layer.randomize.pitch_semitones)
        amp_jitter = 1 + random.uniform(-layer.randomize.amp_pct, layer.randomize.amp_pct)
        osc = self._generate_waveform(layer, layer_samples, layer_pitch)
        env = _render_envelope(layer.envelope, layer_samples)
        rendered = osc * env * layer.amp * amp_jitter
        if layer.lp_hz:
            rendered = self._low_pass(rendered, layer.lp_hz)
        if start_offset:
            padded = np.zeros(total_samples, dtype=np.float32)
            padded[start_offset:start_offset + rendered.size] = rendered
            return padded
        return rendered

    def _generate_waveform(self, layer: LayerSpec, samples: int, pitch_semitones: float) -> np.ndarray:
        t = np.arange(samples) / SAMPLE_RATE
        if layer.layer_type == "noise":
            waveform = np.random.uniform(-1.0, 1.0, size=samples)
            return waveform.astype(np.float32)
        base_freq = layer.freq_hz or 440.0
        ratio = _equal_tempered_ratio(pitch_semitones)
        freq = base_freq * ratio
        if layer.pitch_glide:
            start_ratio = _equal_tempered_ratio(pitch_semitones + layer.pitch_glide[0])
            end_ratio = _equal_tempered_ratio(pitch_semitones + layer.pitch_glide[1])
            freq_envelope = np.linspace(base_freq * start_ratio, base_freq * end_ratio, samples)
            phase = 2 * math.pi * np.cumsum(freq_envelope) / SAMPLE_RATE
        else:
            phase = 2 * math.pi * freq * t
        if layer.layer_type == "sine":
            waveform = np.sin(phase)
        elif layer.layer_type == "triangle":
            waveform = 2 * np.arcsin(np.sin(phase)) / math.pi
        elif layer.layer_type == "square":
            waveform = np.sign(np.sin(phase))
        else:  # osc generic fallback
            waveform = np.sin(phase)
        return waveform.astype(np.float32)

    def _low_pass(self, data: np.ndarray, cutoff_hz: float) -> np.ndarray:
        rc = 1.0 / (2 * math.pi * cutoff_hz)
        dt = 1.0 / SAMPLE_RATE
        alpha = dt / (rc + dt)
        out = np.zeros_like(data)
        for i, sample in enumerate(data):
            if i == 0:
                out[i] = alpha * sample
            else:
                out[i] = out[i - 1] + alpha * (sample - out[i - 1])
        return out
