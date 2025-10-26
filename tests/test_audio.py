import time

import numpy as np
import pytest

from audio.sfx import SFX
from config import HEIGHT, WIDTH


@pytest.fixture(scope="module", autouse=True)
def seed_random():
    np.random.seed(0)
    yield


@pytest.fixture()
def sfx():
    return SFX(enable_audio=False)


def test_sfx_api_smoke(sfx):
    assert hasattr(sfx, "play")
    assert hasattr(sfx, "play_loop")
    assert hasattr(sfx, "stop_loop")
    assert hasattr(sfx, "duck")
    assert hasattr(sfx, "update")


def test_cooldown_prevents_spam(sfx):
    assert sfx.play("hit")
    assert not sfx.play("hit")


def test_variant_rotation(sfx):
    spec = sfx._catalog.get_spec("hit")  # type: ignore[attr-defined]
    first = sfx._next_variant(spec)
    second = sfx._next_variant(spec)
    assert first != second
    # ensure cycle resets
    third = sfx._next_variant(spec)
    assert third == first


def test_equal_power_pan_math(sfx):
    spec = sfx._catalog.get_spec("hit")  # type: ignore[attr-defined]
    left, right = sfx._pan_gains(spec, (WIDTH // 2, HEIGHT // 2), (WIDTH, HEIGHT))  # type: ignore[attr-defined]
    assert pytest.approx(left, rel=1e-3) == pytest.approx(right, rel=1e-3)
    left_edge = sfx._pan_gains(spec, (0, HEIGHT // 2), (WIDTH, HEIGHT))  # type: ignore[attr-defined]
    assert left_edge[0] > 0.99 and left_edge[1] < 0.05


def test_ducking_window_resets(sfx):
    sfx.duck("loops", gain_db=-3.0, ms=10)
    bus = sfx._buses["loops"]
    bus.duck_end = time.monotonic() - 1
    sfx.update(0.016)
    assert bus.duck_gain == pytest.approx(1.0)
