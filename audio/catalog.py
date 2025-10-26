"""Catalog loader for sound events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .utils import log_debug, require


DEFAULTS = {
    "bus": "sfx",
    "loop": False,
    "base_gain": 0.9,
    "cooldown_ms": 50,
    "pan": False,
    "priority": 0,
    "vol_jitter": 0.08,
    "pitch_jitter_semitones": 0.03,
}


@dataclass
class EventSpec:
    """Normalized specification for a catalog event."""

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


class EventCatalog:
    """Load and validate event metadata from JSON."""

    _valid_buses = {"ui", "sfx", "loops", "music"}

    def __init__(self, catalog_path: Path) -> None:
        log_debug(f"catalog:init path={catalog_path}")
        require(catalog_path.exists(), f"Missing catalog file: {catalog_path}")
        with catalog_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        require(isinstance(payload, dict), "Catalog root must be an object")
        self._specs: Dict[str, EventSpec] = {}
        self._variant_indices: Dict[str, int] = {}
        for name, raw in payload.items():
            spec = self._normalize_event(name, raw)
            self._specs[name] = spec
            self._variant_indices[name] = 0

    def _normalize_event(self, name: str, raw: Dict[str, object]) -> EventSpec:
        require(isinstance(raw, dict), f"Event '{name}' must be an object")
        data = DEFAULTS.copy()
        data.update(raw)

        bus = data["bus"]
        require(bus in self._valid_buses, f"Event '{name}' has invalid bus '{bus}'")

        loop = bool(data["loop"])
        base_gain = float(data["base_gain"])
        require(0 <= base_gain <= 1, f"Event '{name}' base_gain out of range")
        cooldown_ms = int(data["cooldown_ms"])
        require(cooldown_ms >= 0, f"Event '{name}' cooldown must be >= 0")
        pan = bool(data["pan"])
        priority = int(data["priority"])
        vol_jitter = float(data["vol_jitter"])
        require(vol_jitter >= 0, f"Event '{name}' vol_jitter must be >= 0")
        pitch_jitter = float(data["pitch_jitter_semitones"])

        recipes: Optional[Iterable[str]] = None
        if "variants" in data:
            variants = data["variants"]
            require(isinstance(variants, list) and variants, f"Event '{name}' variants must be a non-empty list")
            recipes = variants
        elif "recipe" in data:
            recipe = data["recipe"]
            require(isinstance(recipe, str) and recipe, f"Event '{name}' recipe must be a non-empty string")
            recipes = [recipe]

        require(recipes, f"Event '{name}' must declare a recipe or variants")
        recipe_ids = [str(r) for r in recipes]

        return EventSpec(
            name=name,
            bus=bus,
            loop=loop,
            base_gain=base_gain,
            cooldown_ms=cooldown_ms,
            pan=pan,
            priority=priority,
            vol_jitter=vol_jitter,
            pitch_jitter_semitones=pitch_jitter,
            recipe_ids=recipe_ids,
        )

    def get_spec(self, name: str) -> EventSpec:
        """Return the ``EventSpec`` for ``name``."""

        require(name in self._specs, f"Unknown SFX event '{name}'")
        return self._specs[name]

    def next_variant(self, name: str) -> str:
        """Return the next recipe id for ``name`` using round-robin rotation."""

        spec = self.get_spec(name)
        idx = self._variant_indices[name]
        recipe_id = spec.recipe_ids[idx]
        next_idx = (idx + 1) % len(spec.recipe_ids)
        self._variant_indices[name] = next_idx
        log_debug(f"catalog:variant event={name} recipe={recipe_id} next={next_idx}")
        return recipe_id

    def events(self) -> List[str]:
        """List all catalogued event names."""

        return sorted(self._specs)
