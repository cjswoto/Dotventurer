"""Sound recipe loader and validation logic."""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from audio.logging import log_lines


@dataclass(frozen=True)
class EnvelopeSpec:
    attack_ms: float
    decay_ms: float
    sustain: float
    release_ms: float


@dataclass(frozen=True)
class RandomizeSpec:
    pitch_semitones: float = 0.0
    amp_pct: float = 0.0
    start_ms: float = 0.0


@dataclass(frozen=True)
class LayerSpec:
    layer_type: str
    waveform: str
    freq_hz: Optional[float]
    lp_hz: Optional[float]
    amp: float
    env: EnvelopeSpec
    pitch_glide: Optional[List[float]] = None
    randomize: RandomizeSpec = field(default_factory=RandomizeSpec)


@dataclass(frozen=True)
class RecipeSpec:
    recipe_id: str
    duration_ms: float
    loop: bool
    loop_length_ms: Optional[float]
    headroom_db: float
    layers: List[LayerSpec]
    has_randomization: bool


class RecipeError(RuntimeError):
    """Raised when recipe data is malformed."""


class SFXRecipes:
    """Load procedural recipe definitions from JSON or YAML."""

    def __init__(self, path: str | Path) -> None:
        log_lines([f"SFXRecipes.__init__ path={path}"])
        self._path = Path(path)
        self._recipes: Dict[str, RecipeSpec] = {}
        self._load()

    def _load(self) -> None:
        log_lines(["SFXRecipes._load start"])
        if not self._path.exists():
            raise RecipeError(f"Recipe file not found: {self._path}")
        raw_data = self._parse_file(self._path)
        if not isinstance(raw_data, dict):
            raise RecipeError("Recipe root must be an object")
        for recipe_id, payload in raw_data.items():
            spec = self._normalize_recipe(recipe_id, payload)
            self._recipes[recipe_id] = spec
        log_lines(["SFXRecipes._load complete"])

    def _parse_file(self, path: Path):
        suffix = path.suffix.lower()
        with path.open("r", encoding="utf-8") as handle:
            if suffix in {".json"}:
                return json.load(handle)
            if suffix in {".yaml", ".yml"}:
                yaml_module = importlib.import_module("yaml")
                return yaml_module.safe_load(handle)
            raise RecipeError(f"Unsupported recipe format: {suffix}")

    def _normalize_recipe(self, recipe_id: str, payload: Optional[dict]) -> RecipeSpec:
        log_lines([f"SFXRecipes._normalize_recipe id={recipe_id}"])
        if payload is None:
            raise RecipeError(f"Recipe '{recipe_id}' must be an object")
        if not isinstance(payload, dict):
            raise RecipeError(f"Recipe '{recipe_id}' must be an object")
        duration_ms = float(payload.get("duration_ms", 500.0))
        if duration_ms <= 0:
            raise RecipeError(f"Recipe '{recipe_id}' duration must be positive")
        loop = bool(payload.get("loop", False))
        loop_length_ms_raw = payload.get("loop_length_ms")
        loop_length_ms = float(loop_length_ms_raw) if loop_length_ms_raw is not None else None
        headroom_db = float(payload.get("headroom_db", -6.0))
        layers_raw = payload.get("layers", [])
        if not isinstance(layers_raw, list) or not layers_raw:
            raise RecipeError(f"Recipe '{recipe_id}' must define at least one layer")
        layers = [self._normalize_layer(recipe_id, idx, layer) for idx, layer in enumerate(layers_raw)]
        has_randomization = any(
            layer.randomize.pitch_semitones > 0
            or layer.randomize.amp_pct > 0
            or layer.randomize.start_ms > 0
            for layer in layers
        )
        return RecipeSpec(
            recipe_id=recipe_id,
            duration_ms=duration_ms,
            loop=loop,
            loop_length_ms=loop_length_ms,
            headroom_db=headroom_db,
            layers=layers,
            has_randomization=has_randomization,
        )

    def _normalize_layer(self, recipe_id: str, idx: int, payload: dict) -> LayerSpec:
        if not isinstance(payload, dict):
            raise RecipeError(f"Recipe '{recipe_id}' layer {idx} must be an object")
        layer_type = str(payload.get("type", "osc"))
        if layer_type not in {"osc", "noise"}:
            raise RecipeError(f"Recipe '{recipe_id}' layer {idx} has invalid type '{layer_type}'")
        waveform = str(payload.get("wave", "sine"))
        if layer_type == "osc" and waveform not in {"sine", "triangle", "square"}:
            raise RecipeError(
                f"Recipe '{recipe_id}' layer {idx} has invalid wave '{waveform}'"
            )
        if layer_type == "noise":
            waveform = "noise"
        freq_hz = payload.get("freq_hz")
        lp_hz = payload.get("lp_hz")
        if layer_type == "osc" and freq_hz is None:
            raise RecipeError(f"Recipe '{recipe_id}' layer {idx} requires freq_hz")
        amp = float(payload.get("amp", 1.0))
        if amp <= 0:
            raise RecipeError(f"Recipe '{recipe_id}' layer {idx} amp must be positive")
        env_payload = payload.get("env") or {}
        env = self._normalize_env(recipe_id, idx, env_payload)
        pitch_glide = payload.get("pitch_glide")
        if pitch_glide is not None:
            if not isinstance(pitch_glide, list) or len(pitch_glide) != 2:
                raise RecipeError(
                    f"Recipe '{recipe_id}' layer {idx} pitch_glide must be a [start, end] list"
                )
            pitch_glide = [float(pitch_glide[0]), float(pitch_glide[1])]
        randomize_payload = payload.get("randomize") or {}
        randomize = self._normalize_randomize(recipe_id, idx, randomize_payload)
        return LayerSpec(
            layer_type=layer_type,
            waveform=waveform,
            freq_hz=float(freq_hz) if freq_hz is not None else None,
            lp_hz=float(lp_hz) if lp_hz is not None else None,
            amp=amp,
            env=env,
            pitch_glide=pitch_glide,
            randomize=randomize,
        )

    def _normalize_env(self, recipe_id: str, idx: int, payload: dict) -> EnvelopeSpec:
        attack_ms = float(payload.get("attack_ms", 8.0))
        decay_ms = float(payload.get("decay_ms", 40.0))
        sustain = float(payload.get("sustain", 0.6))
        release_ms = float(payload.get("release_ms", 60.0))
        if attack_ms < 0 or decay_ms < 0 or release_ms < 0:
            raise RecipeError(f"Recipe '{recipe_id}' layer {idx} envelope times must be >= 0")
        if sustain < 0 or sustain > 1:
            raise RecipeError(f"Recipe '{recipe_id}' layer {idx} sustain must be 0..1")
        return EnvelopeSpec(
            attack_ms=attack_ms,
            decay_ms=decay_ms,
            sustain=sustain,
            release_ms=release_ms,
        )

    def _normalize_randomize(self, recipe_id: str, idx: int, payload: dict) -> RandomizeSpec:
        pitch = float(payload.get("pitch_semitones", 0.0))
        amp = float(payload.get("amp_pct", 0.0))
        start = float(payload.get("start_ms", 0.0))
        if pitch < 0 or amp < 0 or start < 0:
            raise RecipeError(
                f"Recipe '{recipe_id}' layer {idx} randomize values must be non-negative"
            )
        return RandomizeSpec(pitch_semitones=pitch, amp_pct=amp, start_ms=start)

    # Public API -------------------------------------------------------
    def get(self, recipe_id: str) -> RecipeSpec:
        if recipe_id not in self._recipes:
            raise KeyError(recipe_id)
        return self._recipes[recipe_id]

    def recipes(self) -> Iterable[RecipeSpec]:
        return self._recipes.values()
