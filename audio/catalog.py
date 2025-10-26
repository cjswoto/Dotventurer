"""Event catalog loader for procedural SFX events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from audio.logging import log_lines

ALLOWED_BUSES = {"ui", "sfx", "loops", "music"}


@dataclass(frozen=True)
class EventSpec:
    """Normalized data for a single sound event."""

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


class CatalogError(RuntimeError):
    """Raised when catalog data is malformed."""


class SFXCatalog:
    """Load and expose the procedural audio event catalog."""

    def __init__(self, path: str | Path) -> None:
        log_lines([f"SFXCatalog.__init__ path={path}"])
        self._path = Path(path)
        self._specs: Dict[str, EventSpec] = {}
        self._variant_indices: Dict[str, int] = {}
        self._load()

    # Internal helpers -------------------------------------------------
    def _load(self) -> None:
        log_lines(["SFXCatalog._load start"])
        if not self._path.exists():
            raise CatalogError(f"Catalog file not found: {self._path}")
        with self._path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise CatalogError("Catalog root must be an object")
        for name, raw in data.items():
            spec = self._normalize_event(name, raw)
            self._specs[name] = spec
            self._variant_indices[name] = 0
        log_lines(["SFXCatalog._load complete"])

    def _normalize_event(self, name: str, raw: Optional[dict]) -> EventSpec:
        log_lines([f"SFXCatalog._normalize_event name={name}"])
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise CatalogError(f"Event '{name}' must be an object")

        bus = str(raw.get("bus", "sfx")).lower()
        if bus not in ALLOWED_BUSES:
            raise CatalogError(f"Event '{name}' has invalid bus '{bus}'")

        loop = bool(raw.get("loop", False))
        base_gain = float(raw.get("base_gain", 0.9))
        if not 0 <= base_gain <= 1:
            raise CatalogError(f"Event '{name}' base_gain must be 0..1")
        cooldown_ms = int(raw.get("cooldown_ms", 50))
        pan = bool(raw.get("pan", False))
        priority = int(raw.get("priority", 0))
        vol_jitter = float(raw.get("vol_jitter", 0.08))
        if vol_jitter < 0:
            raise CatalogError(f"Event '{name}' vol_jitter must be >= 0")
        pitch_jitter_semitones = float(raw.get("pitch_jitter_semitones", 0.03))
        recipe_ids = self._extract_recipes(name, raw)
        if not recipe_ids:
            raise CatalogError(f"Event '{name}' is missing recipe ids")
        return EventSpec(
            name=name,
            bus=bus,
            loop=loop,
            base_gain=base_gain,
            cooldown_ms=cooldown_ms,
            pan=pan,
            priority=priority,
            vol_jitter=vol_jitter,
            pitch_jitter_semitones=pitch_jitter_semitones,
            recipe_ids=recipe_ids,
        )

    def _extract_recipes(self, name: str, raw: dict) -> List[str]:
        recipe = raw.get("recipe")
        variants = raw.get("variants")
        if recipe and variants:
            raise CatalogError(
                f"Event '{name}' cannot define both 'recipe' and 'variants'"
            )
        if variants is not None:
            if not isinstance(variants, list) or not variants:
                raise CatalogError(f"Event '{name}' variants must be a non-empty list")
            ids = [str(item) for item in variants]
            return ids
        if recipe is None:
            return []
        return [str(recipe)]

    # Public API -------------------------------------------------------
    def events(self) -> Iterable[EventSpec]:
        return self._specs.values()

    def get_spec(self, event: str) -> EventSpec:
        if event not in self._specs:
            raise KeyError(event)
        return self._specs[event]

    def next_recipe_id(self, event: str) -> str:
        spec = self.get_spec(event)
        if len(spec.recipe_ids) == 1:
            return spec.recipe_ids[0]
        index = self._variant_indices[event]
        recipe_id = spec.recipe_ids[index]
        self._variant_indices[event] = (index + 1) % len(spec.recipe_ids)
        return recipe_id
