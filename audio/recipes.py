"""Recipe loader for procedural audio."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config import AUDIO_LOG_ENABLED

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - yaml optional
    yaml = None



def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


DEFAULT_ENV = {"attack_ms": 8.0, "decay_ms": 0.0, "sustain": 1.0, "release_ms": 40.0}


def _log(message: str) -> None:
    if not AUDIO_LOG_ENABLED:
        return
    os.makedirs("logs", exist_ok=True)
    with open("logs/debug.txt", "a", encoding="utf-8") as handle:
        handle.write(f"[{_timestamp()}][recipes] {message}\n")


@dataclass
class LayerSpec:
    """Represents a single layer within a recipe."""

    layer_type: str
    amp: float
    freq_hz: Optional[float] = None
    lp_hz: Optional[float] = None
    env: Dict[str, float] = field(default_factory=dict)
    glide: Optional[Dict[str, float]] = None
    randomize: Optional[Dict[str, float]] = None


@dataclass
class RecipeSpec:
    """High-level recipe definition used by the renderer."""

    recipe_id: str
    duration_ms: float
    loop: bool
    loop_length_ms: Optional[float]
    headroom_db: float
    layers: List[LayerSpec]


class RecipeLibrary:
    """Container for recipe specs."""

    def __init__(self, recipes: Dict[str, RecipeSpec]):
        self._recipes = recipes

    def get(self, recipe_id: str) -> RecipeSpec:
        if recipe_id not in self._recipes:
            raise KeyError(f"Unknown recipe '{recipe_id}'")
        return self._recipes[recipe_id]


class RecipeLoader:
    """Loader for JSON or YAML recipe definitions."""

    def __init__(self, path: str):
        self.path = path

    def load(self) -> RecipeLibrary:
        raw = self._read()
        recipes: Dict[str, RecipeSpec] = {}
        pending = set(raw.keys())
        while pending:
            recipe_id = pending.pop()
            spec = self._build(recipe_id, raw, recipes)
            recipes[recipe_id] = spec
        return RecipeLibrary(recipes)

    def _read(self) -> Dict[str, Dict[str, object]]:
        ext = os.path.splitext(self.path)[1].lower()
        _log(f"loading recipes from {self.path}")
        with open(self.path, "r", encoding="utf-8") as handle:
            if ext in (".yaml", ".yml"):
                if yaml is None:
                    raise RuntimeError("PyYAML required to load YAML recipes")
                data = yaml.safe_load(handle)
            else:
                data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("Recipe file must contain a mapping of id -> spec")
        return data

    def _build(
        self,
        recipe_id: str,
        source: Dict[str, Dict[str, object]],
        cache: Dict[str, RecipeSpec],
    ) -> RecipeSpec:
        if recipe_id in cache:
            return cache[recipe_id]
        if recipe_id not in source:
            raise KeyError(f"Recipe '{recipe_id}' not found")

        payload = dict(source[recipe_id])
        parent_id = payload.pop("extends", None)
        base: Optional[RecipeSpec] = None
        if parent_id:
            base = self._build(str(parent_id), source, cache)

        duration_ms = float(payload.get("duration_ms", getattr(base, "duration_ms", 500.0)))
        loop = bool(payload.get("loop", getattr(base, "loop", False)))
        loop_length_ms = payload.get("loop_length_ms", getattr(base, "loop_length_ms", None))
        headroom_db = float(payload.get("headroom_db", getattr(base, "headroom_db", -6.0)))
        layers_data = payload.get("layers", None)
        layers: List[LayerSpec]
        if layers_data is None and base is not None:
            layers = base.layers
        else:
            if not isinstance(layers_data, list):
                raise ValueError(f"Recipe '{recipe_id}' layers must be a list")
            layers = [self._parse_layer(item) for item in layers_data]

        spec = RecipeSpec(
            recipe_id=recipe_id,
            duration_ms=duration_ms,
            loop=loop,
            loop_length_ms=float(loop_length_ms) if loop_length_ms is not None else None,
            headroom_db=headroom_db,
            layers=layers,
        )
        _log(f"built recipe {recipe_id} with {len(layers)} layers")
        return spec

    def _parse_layer(self, payload: Dict[str, object]) -> LayerSpec:
        if not isinstance(payload, dict):
            raise ValueError("Layer definition must be a mapping")
        layer_type = str(payload.get("type", "osc")).lower()
        valid_types = {"osc", "noise", "sine", "triangle", "square"}
        if layer_type not in valid_types:
            raise ValueError(f"Unsupported layer type '{layer_type}'")
        amp = float(payload.get("amp", 1.0))
        if not 0 <= amp <= 1:
            raise ValueError("Layer amplitude must be in 0..1")
        freq = payload.get("freq_hz")
        lp = payload.get("lp_hz")
        env = dict(DEFAULT_ENV)
        env.update(payload.get("env", {}))
        glide = payload.get("glide")
        randomize = payload.get("randomize")
        return LayerSpec(
            layer_type=layer_type,
            amp=amp,
            freq_hz=float(freq) if freq is not None else None,
            lp_hz=float(lp) if lp is not None else None,
            env={
                "attack_ms": float(env.get("attack_ms", DEFAULT_ENV["attack_ms"])),
                "decay_ms": float(env.get("decay_ms", DEFAULT_ENV["decay_ms"])),
                "sustain": float(env.get("sustain", DEFAULT_ENV["sustain"])),
                "release_ms": float(env.get("release_ms", DEFAULT_ENV["release_ms"])),
            },
            glide={k: float(v) for k, v in (glide or {}).items()},
            randomize={k: float(v) for k, v in (randomize or {}).items()},
        )


def load_recipes(path: str) -> RecipeLibrary:
    """Convenience helper."""
    return RecipeLoader(path).load()
