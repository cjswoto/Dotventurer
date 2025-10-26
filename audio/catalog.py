"""Catalog loader for procedural audio events."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config import AUDIO_LOG_ENABLED


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


DEFAULT_EVENT = {
    "bus": "sfx",
    "loop": False,
    "cooldown_ms": 50,
    "pan": False,
    "base_gain": 0.9,
    "priority": 0,
    "vol_jitter": 0.08,
    "pitch_jitter_semitones": 0.03,
}

VALID_BUSES = {"ui", "sfx", "loops", "music"}


def _log(message: str) -> None:
    if not AUDIO_LOG_ENABLED:
        return
    os.makedirs("logs", exist_ok=True)
    with open("logs/debug.txt", "a", encoding="utf-8") as handle:
        handle.write(f"[{_timestamp()}][catalog] {message}\n")


@dataclass
class EventSpec:
    """Normalized event specification."""

    name: str
    bus: str
    loop: bool
    base_gain: float
    cooldown_ms: int
    pan: bool
    priority: int
    vol_jitter: float
    pitch_jitter_semitones: float
    recipe_ids: List[str]
    _next_variant: int = field(default=0, init=False, repr=False)

    def next_recipe_id(self) -> Optional[str]:
        """Return the next recipe id, handling round-robin rotation."""
        if not self.recipe_ids:
            return None
        recipe_id = self.recipe_ids[self._next_variant % len(self.recipe_ids)]
        self._next_variant += 1
        return recipe_id


class Catalog:
    """Container for loaded event specifications."""

    def __init__(self, events: Dict[str, EventSpec]):
        self._events = events

    def get_spec(self, event: str) -> EventSpec:
        if event not in self._events:
            raise KeyError(f"Unknown SFX event '{event}'")
        return self._events[event]


class CatalogLoader:
    """Loader responsible for parsing and validating catalog JSON."""

    def __init__(self, path: str):
        self.path = path

    def load(self) -> Catalog:
        _log(f"loading catalog from {self.path}")
        with open(self.path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        events: Dict[str, EventSpec] = {}
        for name, payload in raw.items():
            spec = self._normalise(name, payload)
            events[name] = spec
        return Catalog(events)

    def _normalise(self, name: str, payload: Dict[str, object]) -> EventSpec:
        data = dict(DEFAULT_EVENT)
        data.update(payload or {})

        bus = str(data["bus"]).lower()
        if bus not in VALID_BUSES:
            raise ValueError(f"Event '{name}' has invalid bus '{bus}'")

        loop = bool(data["loop"])
        cooldown = int(data["cooldown_ms"])
        base_gain = float(data.get("base_gain", 0.9))
        if not 0.0 <= base_gain <= 1.0:
            raise ValueError(f"Event '{name}' base_gain must be 0..1")

        pan = bool(data["pan"])
        priority = int(data.get("priority", 0))
        vol_jitter = float(data.get("vol_jitter", DEFAULT_EVENT["vol_jitter"]))
        pitch_jitter = float(data.get("pitch_jitter_semitones", DEFAULT_EVENT["pitch_jitter_semitones"]))

        recipes_field = data.get("recipe")
        variants_field = data.get("variants")
        recipe_ids: List[str]
        if variants_field:
            if not isinstance(variants_field, list):
                raise ValueError(f"Event '{name}' variants must be a list of recipe ids")
            recipe_ids = [str(v) for v in variants_field]
        elif recipes_field:
            recipe_ids = [str(recipes_field)]
        else:
            raise ValueError(f"Event '{name}' requires a recipe or variants list")

        _log(f"normalised event {name} -> {recipe_ids}")
        return EventSpec(
            name=name,
            bus=bus,
            loop=loop,
            base_gain=base_gain,
            cooldown_ms=cooldown,
            pan=pan,
            priority=priority,
            vol_jitter=vol_jitter,
            pitch_jitter_semitones=pitch_jitter,
            recipe_ids=recipe_ids,
        )


def load_catalog(path: str) -> Catalog:
    """Convenience helper."""
    return CatalogLoader(path).load()
