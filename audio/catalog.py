"""Catalog loader for procedural audio events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ._logging import log_line

_DEFAULTS = {
    "bus": "sfx",
    "loop": False,
    "cooldown_ms": 50,
    "pan": False,
    "base_gain": 0.9,
    "vol_jitter": 0.08,
    "pitch_jitter_semitones": 0.03,
}

_VALID_BUSES = {"ui", "sfx", "loops", "music"}


@dataclass(frozen=True)
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


class Catalog:
    """Load and provide access to the SFX catalog."""

    def __init__(self, path: Path) -> None:
        self._path = path
        log_line("loading catalog", context="Catalog", data={"path": str(path)})
        if not path.exists():
            raise FileNotFoundError(path)
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            raise ValueError("sfx_catalog.json must contain an object at the top level")
        self._events: Dict[str, EventSpec] = {}
        for name, spec in raw.items():
            event = self._normalize_event(name, spec)
            self._events[event.name] = event
        log_line("catalog loaded", context="Catalog", data={"events": len(self._events)})

    def _normalize_event(self, name: str, data: dict) -> EventSpec:
        if not isinstance(data, dict):
            raise ValueError(f"Event '{name}' must be an object")
        values = {**_DEFAULTS, **data}
        bus = str(values["bus"]).lower()
        if bus not in _VALID_BUSES:
            raise ValueError(f"Event '{name}' references invalid bus '{bus}'")
        loop = bool(values["loop"])
        cooldown = int(values["cooldown_ms"])
        base_gain = float(values["base_gain"])
        if not 0 <= base_gain <= 1:
            raise ValueError(f"Event '{name}' base_gain must be 0..1")
        vol_jitter = float(values.get("vol_jitter", _DEFAULTS["vol_jitter"]))
        pitch_jitter = float(values.get("pitch_jitter_semitones", _DEFAULTS["pitch_jitter_semitones"]))
        priority = int(values.get("priority", 0))
        pan = bool(values["pan"])
        recipe_field = values.get("recipe")
        variants_field = values.get("variants")
        recipe_ids: List[str]
        if variants_field:
            if not isinstance(variants_field, list):
                raise ValueError(f"Event '{name}' variants must be a list")
            recipe_ids = [str(v) for v in variants_field]
        elif recipe_field:
            recipe_ids = [str(recipe_field)]
        else:
            raise ValueError(f"Event '{name}' must specify a recipe or variants")
        if not recipe_ids:
            raise ValueError(f"Event '{name}' has no recipe ids")
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

    def get_spec(self, event: str) -> EventSpec:
        try:
            return self._events[event]
        except KeyError as exc:
            raise KeyError(f"Unknown SFX event '{event}'") from exc

    def events(self) -> Iterable[EventSpec]:
        return self._events.values()

    @classmethod
    def load_default(cls, root: Optional[Path] = None) -> "Catalog":
        base = root or Path(".")
        path = base / "assets" / "sfx_catalog.json"
        return cls(path)
