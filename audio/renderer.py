"""Procedural audio renderer – turns recipes into NumPy buffers."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Optional

import numpy as np

from audio.logging import log_lines
from audio.recipes import EnvelopeSpec, LayerSpec, RecipeSpec, RandomizeSpec

SAMPLE_RATE = 48_000
TWO_PI = 2 * math.pi


@dataclass(frozen=True)
class RenderResult:
    data: np.ndarray
    sample_rate: int


def db_to_linear(db: float) -> float:
    return 10 ** (db / 20.0)


def semitone_ratio(semitones: float) -> float:
    return 2 ** (semitones / 12.0)


class Renderer:
    """Render recipes to floating-point stereo buffers."""

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        log_lines([f"Renderer.__init__ sample_rate={sample_rate}"])
        self.sample_rate = sample_rate

    def render(
        self,
        recipe: RecipeSpec,
        rng: Optional[random.Random] = None,
        pitch_semitones: float = 0.0,
        amp_scale: float = 1.0,
    ) -> RenderResult:
        log_lines([f"Renderer.render recipe={recipe.recipe_id}"])
        rng = rng or random.Random()
        total_samples = max(1, int(self.sample_rate * recipe.duration_ms / 1000.0))
        mix = np.zeros(total_samples, dtype=np.float32)
        for layer in recipe.layers:
            layer_buffer = self._render_layer(
                layer=layer,
                total_samples=total_samples,
                rng=rng,
                global_pitch=pitch_semitones,
            )
            mix[: layer_buffer.shape[0]] += layer_buffer
        peak = float(np.max(np.abs(mix)))
        target = db_to_linear(recipe.headroom_db)
        if peak > 0:
            mix *= target / peak
        mix *= float(amp_scale)
        stereo = np.stack([mix, mix], axis=1)
        return RenderResult(data=stereo.astype(np.float32), sample_rate=self.sample_rate)

    # ------------------------------------------------------------------
    def _render_layer(
        self,
        layer: LayerSpec,
        total_samples: int,
        rng: random.Random,
        global_pitch: float,
    ) -> np.ndarray:
        env = self._adsr(layer.env, total_samples)
        start_offset = self._random_start_offset(layer.randomize, rng)
        amp_scale = self._random_amp(layer.randomize, rng)
        semitone_offset = self._random_pitch(layer.randomize, rng) + global_pitch
        waveform = self._generate_wave(layer, total_samples, semitone_offset, rng)
        waveform *= env
        waveform *= layer.amp * amp_scale
        if layer.lp_hz:
            waveform = self._low_pass(waveform, layer.lp_hz)
        if start_offset == 0:
            return waveform
        shifted = np.zeros_like(waveform)
        if start_offset > 0:
            dest_start = min(total_samples, start_offset)
            length = total_samples - dest_start
            if length > 0:
                shifted[dest_start:dest_start + length] = waveform[:length]
        else:
            src_start = min(total_samples, -start_offset)
            length = total_samples - src_start
            if length > 0:
                shifted[:length] = waveform[src_start:src_start + length]
        return shifted

    def _adsr(self, env: EnvelopeSpec, total_samples: int) -> np.ndarray:
        attack = int(self.sample_rate * env.attack_ms / 1000.0)
        decay = int(self.sample_rate * env.decay_ms / 1000.0)
        release = int(self.sample_rate * env.release_ms / 1000.0)
        sustain = env.sustain
        envelope = np.zeros(total_samples, dtype=np.float32)
        cursor = 0
        if attack > 0:
            attack_end = min(total_samples, attack)
            envelope[:attack_end] = np.linspace(0.0, 1.0, attack_end, endpoint=False)
            cursor = attack_end
        else:
            envelope[0] = 1.0
            cursor = 1
        if cursor < total_samples and decay > 0:
            decay_end = min(total_samples, cursor + decay)
            envelope[cursor:decay_end] = np.linspace(1.0, sustain, decay_end - cursor, endpoint=False)
            cursor = decay_end
        if cursor < total_samples:
            release_start = max(cursor, total_samples - release)
            if release_start > cursor:
                envelope[cursor:release_start] = sustain
            if release > 0:
                release_range = total_samples - release_start
                if release_range > 0:
                    envelope[release_start:total_samples] = np.linspace(
                        sustain, 0.0, release_range, endpoint=False
                    )
            else:
                envelope[release_start:total_samples] = sustain
        if total_samples > 0:
            envelope[-1] = 0.0
        return envelope

    def _random_start_offset(self, randomize: RandomizeSpec, rng: random.Random) -> int:
        if randomize.start_ms <= 0:
            return 0
        offset_ms = rng.uniform(-randomize.start_ms, randomize.start_ms)
        return int(self.sample_rate * offset_ms / 1000.0)

    def _random_amp(self, randomize: RandomizeSpec, rng: random.Random) -> float:
        if randomize.amp_pct <= 0:
            return 1.0
        delta = rng.uniform(-randomize.amp_pct, randomize.amp_pct) / 100.0
        return 1.0 + delta

    def _random_pitch(self, randomize: RandomizeSpec, rng: random.Random) -> float:
        if randomize.pitch_semitones <= 0:
            return 0.0
        return rng.uniform(-randomize.pitch_semitones, randomize.pitch_semitones)

    def _generate_wave(
        self,
        layer: LayerSpec,
        total_samples: int,
        semitone_offset: float,
        rng: random.Random,
    ) -> np.ndarray:
        if layer.layer_type == "noise":
            return self._generate_noise(total_samples, rng)
        freq_envelope = self._frequency_array(layer, total_samples, semitone_offset)
        phase = TWO_PI * np.cumsum(freq_envelope) / self.sample_rate
        if layer.waveform == "square":
            return np.sign(np.sin(phase)).astype(np.float32)
        if layer.waveform == "triangle":
            return (2.0 / math.pi * np.arcsin(np.sin(phase))).astype(np.float32)
        return np.sin(phase).astype(np.float32)

    def _frequency_array(
        self,
        layer: LayerSpec,
        total_samples: int,
        semitone_offset: float,
    ) -> np.ndarray:
        base_freq = float(layer.freq_hz or 0.0)
        if layer.pitch_glide:
            start, end = layer.pitch_glide
            semitone_curve = np.linspace(start, end, total_samples, endpoint=False)
        else:
            semitone_curve = np.zeros(total_samples)
        semitone_curve += semitone_offset
        ratios = semitone_ratio(semitone_curve)
        return base_freq * ratios

    def _generate_noise(self, total_samples: int, rng: random.Random) -> np.ndarray:
        seed = rng.randint(0, 2**32 - 1)
        noise_rng = np.random.default_rng(seed)
        return noise_rng.uniform(-1.0, 1.0, total_samples).astype(np.float32)

    def _low_pass(self, data: np.ndarray, cutoff_hz: float) -> np.ndarray:
        if cutoff_hz <= 0:
            return data
        rc = 1.0 / (2 * math.pi * cutoff_hz)
        dt = 1.0 / self.sample_rate
        alpha = dt / (rc + dt)
        filtered = np.zeros_like(data)
        for i, sample in enumerate(data):
            if i == 0:
                filtered[i] = alpha * sample
            else:
                filtered[i] = filtered[i - 1] + alpha * (sample - filtered[i - 1])
        return filtered
