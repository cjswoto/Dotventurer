"""Load and normalise the SFX catalog definitions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .logging_utils import log_line

_DEFAULT_PATH = Path("assets/sfx_catalog.json")
_DEFAULT_BUS = "sfx"
_DEFAULT_COOLDOWN_MS = 50
_DEFAULT_PRIORITY = 50
_DEFAULT_VOL_JITTER = 0.08
_DEFAULT_PITCH_JITTER = 0.5
_DEFAULT_BASE_GAIN = -3.0


@dataclass
class EventSpec:
    """Normalised event description used by the mixer."""

    name: str
    bus: str = _DEFAULT_BUS
    loop: bool = False
    base_gain: float = _DEFAULT_BASE_GAIN
    cooldown_ms: int = _DEFAULT_COOLDOWN_MS
    pan: bool = False
    priority: int = _DEFAULT_PRIORITY
    vol_jitter: float = _DEFAULT_VOL_JITTER
    pitch_jitter_semitones: float = _DEFAULT_PITCH_JITTER
    variants: Optional[List[str]] = None

    def copy_for_runtime(self) -> "EventSpec":
        return EventSpec(
            name=self.name,
            bus=self.bus,
            loop=self.loop,
            base_gain=self.base_gain,
            cooldown_ms=self.cooldown_ms,
            pan=self.pan,
            priority=self.priority,
            vol_jitter=self.vol_jitter,
            pitch_jitter_semitones=self.pitch_jitter_semitones,
            variants=list(self.variants) if self.variants else None,
        )


class Catalog:
    """Data-driven store of sound event specifications."""

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path) if path else _DEFAULT_PATH
        self._events: Dict[str, EventSpec] = {}
        self._load()

    # ------------------------------------------------------------------
    def _load(self) -> None:
        log_line(f"Catalog load start: {self.path}")
        if not self.path.exists():
            log_line("Catalog file missing; defaults will be generated on demand")
            return
        with self.path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        for name, data in raw.items():
            self._events[name] = self._normalise(name, data)
        log_line(f"Catalog loaded {len(self._events)} events")

    # ------------------------------------------------------------------
    def _normalise(self, name: str, data: Dict[str, object]) -> EventSpec:
        variants = data.get("variants")
        if variants is not None and not isinstance(variants, list):
            variants = None
        spec = EventSpec(
            name=name,
            bus=str(data.get("bus", _DEFAULT_BUS)).lower(),
            loop=bool(data.get("loop", False)),
            base_gain=float(data.get("base_gain", _DEFAULT_BASE_GAIN)),
            cooldown_ms=int(data.get("cooldown_ms", _DEFAULT_COOLDOWN_MS)),
            pan=bool(data.get("pan", False)),
            priority=int(data.get("priority", _DEFAULT_PRIORITY)),
            vol_jitter=float(data.get("vol_jitter", _DEFAULT_VOL_JITTER)),
            pitch_jitter_semitones=float(
                data.get("pitch_jitter_semitones", _DEFAULT_PITCH_JITTER)
            ),
            variants=variants,
        )
        return spec

    # ------------------------------------------------------------------
    def get(self, event: str) -> EventSpec:
        if event not in self._events:
            log_line(f"Catalog missing '{event}', generating defaults")
            self._events[event] = EventSpec(name=event)
        return self._events[event].copy_for_runtime()

    # ------------------------------------------------------------------
    def events(self) -> Iterable[EventSpec]:
        for spec in self._events.values():
            yield spec.copy_for_runtime()


def load_catalog(path: Optional[str] = None) -> Catalog:
    """Factory helper mirroring legacy entry points."""

    return Catalog(path)
