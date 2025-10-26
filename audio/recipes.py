"""Procedural audio recipe loader and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ._logging import log_line

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None


@dataclass(frozen=True)
class Envelope:
    attack_ms: float
    decay_ms: float
    sustain: float
    release_ms: float


@dataclass(frozen=True)
class Randomize:
    pitch_semitones: float = 0.0
    amp_pct: float = 0.0
    start_ms: float = 0.0


@dataclass(frozen=True)
class LayerSpec:
    layer_type: str
    amp: float
    freq_hz: Optional[float] = None
    lp_hz: Optional[float] = None
    wave: str = "sine"
    envelope: Envelope = field(default_factory=lambda: Envelope(10.0, 50.0, 0.0, 60.0))
    pitch_glide: Optional[tuple[float, float]] = None
    randomize: Randomize = field(default_factory=Randomize)


@dataclass(frozen=True)
class RecipeSpec:
    name: str
    duration_ms: float
    loop: bool
    loop_length_ms: Optional[float]
    headroom_db: float
    layers: List[LayerSpec]


class RecipeLibrary:
    """Load and manage procedural sound recipes."""

    def __init__(self, path: Path) -> None:
        self._path = path
        log_line("loading recipes", context="RecipeLibrary", data={"path": str(path)})
        if not path.exists():
            raise FileNotFoundError(path)
        data = self._read_file(path)
        if not isinstance(data, dict):
            raise ValueError("sfx_recipes must contain an object at the top level")
        self._raw = data
        self._recipes: Dict[str, RecipeSpec] = {}
        for name in data:
            self._build_recipe(name, set())
        log_line("recipes ready", context="RecipeLibrary", data={"count": len(self._recipes)})

    def _read_file(self, path: Path):  # type: ignore[override]
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() in {".yaml", ".yml"}:
            if yaml is None:
                raise RuntimeError("PyYAML is required to load YAML recipe files")
            return yaml.safe_load(text)
        return json.loads(text)

    def _build_recipe(self, name: str, visiting: set[str]) -> RecipeSpec:
        if name in self._recipes:
            return self._recipes[name]
        if name in visiting:
            raise ValueError(f"Circular recipe inheritance detected at '{name}'")
        visiting.add(name)
        raw = self._raw.get(name)
        if not isinstance(raw, dict):
            raise KeyError(f"Recipe '{name}' not defined")
        base_id = raw.get("extends")
        base_spec: Optional[RecipeSpec] = None
        if base_id:
            base_spec = self._build_recipe(str(base_id), visiting)
        recipe = self._parse_recipe(name, raw, base_spec)
        self._recipes[name] = recipe
        visiting.remove(name)
        return recipe

    def _parse_recipe(self, name: str, raw: dict, base: Optional[RecipeSpec]) -> RecipeSpec:
        duration_ms = float(raw.get("duration_ms", base.duration_ms if base else 500.0))
        if duration_ms <= 0:
            raise ValueError(f"Recipe '{name}' duration_ms must be positive")
        loop = bool(raw.get("loop", base.loop if base else False))
        loop_length_ms = raw.get("loop_length_ms", base.loop_length_ms if base else None)
        if loop and loop_length_ms is None:
            loop_length_ms = duration_ms
        headroom_db = float(raw.get("headroom_db", base.headroom_db if base else -6.0))
        layers_data = raw.get("layers")
        if layers_data is None:
            layers = list(base.layers) if base else []
        else:
            if not isinstance(layers_data, list):
                raise ValueError(f"Recipe '{name}' layers must be a list")
            parsed = [self._parse_layer(name, layer) for layer in layers_data]
            layers = list(base.layers) + parsed if base else parsed
        return RecipeSpec(
            name=name,
            duration_ms=duration_ms,
            loop=loop,
            loop_length_ms=float(loop_length_ms) if loop_length_ms is not None else None,
            headroom_db=headroom_db,
            layers=layers,
        )

    def _parse_layer(self, recipe: str, data: dict) -> LayerSpec:
        if not isinstance(data, dict):
            raise ValueError(f"Recipe '{recipe}' layer must be an object")
        layer_type = str(data.get("type"))
        if layer_type not in {"osc", "noise"}:
            raise ValueError(f"Recipe '{recipe}' layer has invalid type '{layer_type}'")
        amp = float(data.get("amp", 1.0))
        if amp <= 0:
            raise ValueError(f"Recipe '{recipe}' layer amplitude must be positive")
        freq = data.get("freq_hz")
        lp = data.get("lp_hz")
        if layer_type == "osc":
            if freq is None:
                raise ValueError(f"Recipe '{recipe}' oscillator layer missing freq_hz")
            freq = float(freq)
        elif lp is not None:
            lp = float(lp)
        wave = str(data.get("wave", "sine"))
        if wave not in {"sine", "triangle", "square"}:
            raise ValueError(f"Recipe '{recipe}' layer has invalid wave '{wave}'")
        env_raw = data.get("env", {})
        envelope = Envelope(
            attack_ms=float(env_raw.get("attack_ms", 8.0)),
            decay_ms=float(env_raw.get("decay_ms", 40.0)),
            sustain=float(env_raw.get("sustain", 0.0)),
            release_ms=float(env_raw.get("release_ms", 60.0)),
        )
        if not 0 <= envelope.sustain <= 1:
            raise ValueError(f"Recipe '{recipe}' sustain must be 0..1")
        pitch_glide = None
        if "pitch_glide" in data:
            glide = data["pitch_glide"]
            if not isinstance(glide, (list, tuple)) or len(glide) != 2:
                raise ValueError(f"Recipe '{recipe}' pitch_glide must be [start, end]")
            pitch_glide = (float(glide[0]), float(glide[1]))
        rand_raw = data.get("randomize", {})
        randomize = Randomize(
            pitch_semitones=float(rand_raw.get("pitch_semitones", 0.0)),
            amp_pct=float(rand_raw.get("amp_pct", 0.0)),
            start_ms=float(rand_raw.get("start_ms", 0.0)),
        )
        return LayerSpec(
            layer_type=layer_type,
            amp=amp,
            freq_hz=float(freq) if freq is not None else None,
            lp_hz=float(lp) if lp is not None else None,
            wave=wave,
            envelope=envelope,
            pitch_glide=pitch_glide,
            randomize=randomize,
        )

    def get(self, name: str) -> RecipeSpec:
        try:
            return self._recipes[name]
        except KeyError as exc:
            raise KeyError(f"Unknown recipe '{name}'") from exc

    @classmethod
    def load_default(cls, root: Optional[Path] = None) -> "RecipeLibrary":
        base = root or Path(".")
        path = base / "assets" / "sfx_recipes.json"
        return cls(path)
