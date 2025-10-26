"""Asset discovery and preparation for SFX playback."""

from __future__ import annotations

import contextlib
import re
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np

from .logging_utils import log_line, log_loop

_EVENT_RE = re.compile(r"^(?P<name>[a-zA-Z0-9_]+?)(?:_(?P<index>\d{2}))?$")
_PREFERRED_SAMPLE_RATE = 48000


@dataclass
class AssetVariant:
    """A discrete audio asset variant for an event."""

    event: str
    path: Path
    samples: np.ndarray
    sample_rate: int


class AssetLibrary:
    """Discover, load, and resample SFX assets on demand."""

    def __init__(self, base_path: str = "assets/sfx", enable_audio: bool = True):
        self.base_path = Path(base_path)
        self.enable_audio = enable_audio
        self._assets: Dict[str, List[AssetVariant]] = {}
        self._discover()

    # ------------------------------------------------------------------
    def _discover(self) -> None:
        log_line(f"Discovering audio assets in {self.base_path}")
        if not self.base_path.exists():
            log_line("Asset directory missing; procedural fallback will be used")
            return
        discovered: Dict[str, List[AssetVariant]] = {}
        for wav_path in sorted(self.base_path.glob("*.wav")):
            match = _EVENT_RE.match(wav_path.stem)
            if not match:
                log_line(f"Ignoring unmatched asset name: {wav_path.name}")
                continue
            event = match.group("name")
            variant = self._load_variant(event, wav_path)
            if variant is None:
                continue
            discovered.setdefault(event, []).append(variant)
        for event, variants in discovered.items():
            variants.sort(key=lambda v: v.path.name)
            self._assets[event] = variants
        log_line(f"Asset discovery complete: {len(self._assets)} events")

    # ------------------------------------------------------------------
    def _load_variant(self, event: str, wav_path: Path) -> Optional[AssetVariant]:
        with contextlib.closing(wave.open(str(wav_path), "rb")) as handle:
            channels = handle.getnchannels()
            width = handle.getsampwidth()
            frames = handle.getnframes()
            sample_rate = handle.getframerate()
            raw = handle.readframes(frames)
        dtype = {1: np.int8, 2: np.int16, 4: np.int32}.get(width)
        if dtype is None:
            log_line(f"Unsupported sample width in {wav_path}")
            return None
        data = np.frombuffer(raw, dtype=dtype).astype(np.float32)
        max_abs = np.max(np.abs(data)) if data.size else 0.0
        if max_abs:
            data /= max_abs
        if channels > 1:
            data = data.reshape(-1, channels)
        else:
            data = data.reshape(-1, 1)
        if sample_rate != _PREFERRED_SAMPLE_RATE:
            log_line(
                f"Sample rate mismatch for {wav_path.name}: {sample_rate} Hz (expected {_PREFERRED_SAMPLE_RATE})"
            )
        return AssetVariant(event=event, path=wav_path, samples=data, sample_rate=sample_rate)

    # ------------------------------------------------------------------
    def variants_for(self, event: str, explicit: Optional[Iterable[str]] = None) -> List[AssetVariant]:
        variants: List[AssetVariant] = []
        if explicit:
            for name in explicit:
                wav_path = self.base_path / f"{name}.wav"
                if wav_path.exists():
                    variant = self._load_variant(event, wav_path)
                    if variant:
                        variants.append(variant)
                else:
                    log_line(f"Explicit variant missing: {wav_path}")
        if not variants and event in self._assets:
            variants = list(self._assets[event])
        if variants:
            log_loop(f"Variants for {event}", [v.path.name for v in variants])
        return variants

    # ------------------------------------------------------------------
    def build_sound(self, variant: AssetVariant, pitch_factor: float):
        if not self.enable_audio:
            return None
        import pygame
        from pygame import sndarray

        samples = variant.samples
        if pitch_factor != 1.0:
            samples = _resample(samples, pitch_factor)
        normalised = np.clip(samples, -1.0, 1.0)
        int_samples = np.int16(normalised * 32767)
        if int_samples.ndim == 1 or int_samples.shape[1] == 1:
            buffer_data = int_samples.reshape(-1, 1)
        else:
            buffer_data = int_samples
        sound = sndarray.make_sound(buffer_data.copy(order="C"))
        return sound


def _resample(samples: np.ndarray, factor: float) -> np.ndarray:
    if samples.size == 0 or factor == 1.0:
        return samples
    length = samples.shape[0]
    new_length = max(1, int(round(length / factor)))
    old_positions = np.linspace(0.0, 1.0, num=length, endpoint=False)
    new_positions = np.linspace(0.0, 1.0, num=new_length, endpoint=False)
    if samples.ndim == 1 or samples.shape[1] == 1:
        resampled = np.interp(new_positions, old_positions, samples.reshape(-1))
        return resampled.astype(np.float32).reshape(-1, 1)
    channels = samples.shape[1]
    output = np.zeros((new_length, channels), dtype=np.float32)
    for idx in range(channels):
        output[:, idx] = np.interp(new_positions, old_positions, samples[:, idx])
    return output
