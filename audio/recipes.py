"""Recipe loader for procedural sound definitions."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

try:  # Optional YAML support
    import yaml  # type: ignore
except Exception:  # pragma: no cover - YAML is optional
    yaml = None

from .utils import log_debug, require


@dataclass
class EnvelopeSpec:
    attack_ms: float
    decay_ms: float
    sustain: float
    release_ms: float


@dataclass
class LayerRandomization:
    pitch_semitones: float = 0.0
    amp_pct: float = 0.0
    start_ms: float = 0.0


@dataclass
class LayerSpec:
    layer_type: str
    freq_hz: Optional[float]
    lp_hz: Optional[float]
    amp: float
    envelope: EnvelopeSpec
    pitch_glide: Optional[List[float]]
    start_ms: float
    randomize: LayerRandomization


@dataclass
class RecipeSpec:
    recipe_id: str
    duration_ms: float
    loop: bool
    loop_length_ms: Optional[float]
    headroom_db: float
    layers: List[LayerSpec]


class RecipeLibrary:
    """Load procedural sound recipes."""

    def __init__(self, recipe_path: Path) -> None:
        log_debug(f"recipes:init path={recipe_path}")
        require(recipe_path.exists(), f"Missing recipe file: {recipe_path}")
        raw = self._load_file(recipe_path)
        require(isinstance(raw, dict), "Recipe root must be an object")
        self._recipes: Dict[str, RecipeSpec] = {}
        for name, payload in raw.items():
            resolved = self._resolve_inheritance(name, payload, raw)
            self._recipes[name] = self._normalize_recipe(name, resolved)

    def _load_file(self, path: Path):  # type: ignore[override]
        if path.suffix.lower() in {".yaml", ".yml"}:
            require(yaml is not None, "PyYAML is required to load YAML recipes")
            with path.open("r", encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _resolve_inheritance(self, name: str, payload: Dict[str, object], root: Dict[str, object]) -> Dict[str, object]:
        require(isinstance(payload, dict), f"Recipe '{name}' must be an object")
        if "extends" not in payload:
            return payload
        parent_id = payload["extends"]
        require(isinstance(parent_id, str), f"Recipe '{name}' extends must be a string")
        require(parent_id in root, f"Recipe '{name}' extends missing parent '{parent_id}'")
        parent_payload = self._resolve_inheritance(parent_id, root[parent_id], root)
        merged = deepcopy(parent_payload)
        merged.update({k: v for k, v in payload.items() if k != "extends"})
        return merged

    def _normalize_recipe(self, recipe_id: str, payload: Dict[str, object]) -> RecipeSpec:
        duration = float(payload.get("duration_ms", 500))
        require(duration > 0, f"Recipe '{recipe_id}' duration must be > 0")
        loop = bool(payload.get("loop", False))
        loop_length = payload.get("loop_length_ms")
        loop_length_ms = float(loop_length) if loop_length is not None else None
        if loop:
            require(loop_length_ms is None or loop_length_ms > 0, f"Recipe '{recipe_id}' loop_length must be > 0")
        headroom = float(payload.get("headroom_db", -6.0))

        raw_layers = payload.get("layers")
        require(isinstance(raw_layers, list) and raw_layers, f"Recipe '{recipe_id}' must declare layers")
        layers = [self._normalize_layer(recipe_id, layer_payload) for layer_payload in raw_layers]

        return RecipeSpec(
            recipe_id=recipe_id,
            duration_ms=duration,
            loop=loop,
            loop_length_ms=loop_length_ms,
            headroom_db=headroom,
            layers=layers,
        )

    def _normalize_layer(self, recipe_id: str, payload: Dict[str, object]) -> LayerSpec:
        require(isinstance(payload, dict), f"Recipe '{recipe_id}' layer must be an object")
        layer_type = payload.get("type")
        require(
            layer_type in {"sine", "triangle", "square", "noise"},
            f"Recipe '{recipe_id}' layer has invalid type",
        )
        freq = payload.get("freq_hz")
        freq_hz = float(freq) if freq is not None else None
        lp = payload.get("lp_hz")
        lp_hz = float(lp) if lp is not None else None
        amp = float(payload.get("amp", 1.0))
        require(0 <= amp <= 1.0, f"Recipe '{recipe_id}' layer amp must be 0..1")
        env_payload = payload.get("env", {})
        require(isinstance(env_payload, dict), f"Recipe '{recipe_id}' layer env must be an object")
        env = EnvelopeSpec(
            attack_ms=float(env_payload.get("attack_ms", 8.0)),
            decay_ms=float(env_payload.get("decay_ms", 40.0)),
            sustain=float(env_payload.get("sustain", 0.5)),
            release_ms=float(env_payload.get("release_ms", 50.0)),
        )
        require(0 <= env.sustain <= 1, f"Recipe '{recipe_id}' sustain must be 0..1")
        glide = payload.get("pitch_glide")
        if glide is not None:
            require(
                isinstance(glide, list) and len(glide) == 2,
                f"Recipe '{recipe_id}' pitch_glide must be [start, end]",
            )
            pitch_glide = [float(glide[0]), float(glide[1])]
        else:
            pitch_glide = None
        random_payload = payload.get("randomize", {})
        require(isinstance(random_payload, dict), f"Recipe '{recipe_id}' randomize must be an object")
        randomize = LayerRandomization(
            pitch_semitones=float(random_payload.get("pitch_semitones", 0.0)),
            amp_pct=float(random_payload.get("amp_pct", 0.0)),
            start_ms=float(random_payload.get("start_ms", 0.0)),
        )
        return LayerSpec(
            layer_type=str(layer_type),
            freq_hz=freq_hz,
            lp_hz=lp_hz,
            amp=amp,
            envelope=env,
            pitch_glide=pitch_glide,
            start_ms=float(payload.get("start_ms", 0.0)),
            randomize=randomize,
        )

    def get(self, recipe_id: str) -> RecipeSpec:
        require(recipe_id in self._recipes, f"Unknown recipe '{recipe_id}'")
        return self._recipes[recipe_id]

    def ids(self) -> List[str]:
        return sorted(self._recipes)
