import json
import math

from audio.catalog import load_catalog
from audio.sfx import SFX


def _catalog_path(tmp_path, data):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_catalog_defaults(tmp_path):
    path = _catalog_path(tmp_path, {"known": {"bus": "ui", "cooldown_ms": 120}})
    catalog = load_catalog(path)
    known = catalog.get("known")
    missing = catalog.get("missing")
    assert known.bus == "ui"
    assert known.cooldown_ms == 120
    assert missing.bus == "sfx"
    assert missing.cooldown_ms == 50


def test_cooldown_blocks_fast_replay(tmp_path):
    path = _catalog_path(
        tmp_path,
        {
            "burst": {
                "bus": "sfx",
                "cooldown_ms": 200,
                "vol_jitter": 0.0,
                "pitch_jitter_semitones": 0.0,
            }
        },
    )
    sfx = SFX(enable_audio=False, config_path=path)
    assert sfx.play("burst") is True
    assert sfx.play("burst") is False
    sfx.update(0.21)
    assert sfx.play("burst") is True


def test_voice_priority_and_cap(tmp_path):
    path = _catalog_path(
        tmp_path,
        {
            "low": {"priority": 10, "cooldown_ms": 0},
            "mid": {"priority": 20, "cooldown_ms": 0},
            "high": {"priority": 100, "cooldown_ms": 0},
            "lower": {"priority": 5, "cooldown_ms": 0},
        },
    )
    sfx = SFX(enable_audio=False, config_path=path)
    sfx.buses["sfx"].cap = 2
    assert sfx.play("low") is True
    assert sfx.play("mid") is True
    assert len(sfx._voices["sfx"]) == 2
    assert sfx.play("lower") is False
    assert sfx.play("high") is True
    names = {voice.event for voice in sfx._voices["sfx"]}
    assert "high" in names and "mid" in names
    assert "low" not in names


def test_constant_power_pan(tmp_path):
    path = _catalog_path(
        tmp_path,
        {
            "pan_test": {
                "pan": True,
                "base_gain": 0.0,
                "cooldown_ms": 0,
                "vol_jitter": 0.0,
                "pitch_jitter_semitones": 0.0,
            }
        },
    )
    sfx = SFX(enable_audio=False, config_path=path)
    spec = sfx.catalog.get("pan_test")
    center = sfx._compute_volumes(spec, 1.0, (960, 0), (1920, 1080))
    left = sfx._compute_volumes(spec, 1.0, (0, 0), (1920, 1080))
    right = sfx._compute_volumes(spec, 1.0, (1920, 0), (1920, 1080))
    assert math.isclose(center[0], center[1], rel_tol=1e-6)
    assert left[0] > left[1]
    assert right[1] > right[0]
    total_center = math.sqrt(center[0] ** 2 + center[1] ** 2)
    total_edge = math.sqrt(left[0] ** 2 + left[1] ** 2)
    assert math.isclose(total_center, total_edge, rel_tol=1e-6)
