import sys
import types
import unittest

import numpy as np

# Lightweight pygame stub so audio modules can import without a real dependency
pygame_stub = types.ModuleType("pygame")
pygame_stub.SRCALPHA = 0
pygame_stub.time = types.SimpleNamespace(get_ticks=lambda: 0)
pygame_stub.font = types.SimpleNamespace(
    SysFont=lambda *args, **kwargs: types.SimpleNamespace(render=lambda *a, **k: types.SimpleNamespace(get_width=lambda: 0, get_height=lambda: 0))
)
pygame_stub.mouse = types.SimpleNamespace(get_pos=lambda: (0, 0), get_pressed=lambda: (False, False, False))
pygame_stub.display = types.SimpleNamespace(set_mode=lambda *a, **k: None, Info=lambda: types.SimpleNamespace(current_w=800, current_h=600), flip=lambda: None)
pygame_stub.event = types.SimpleNamespace(get=lambda: [], Event=object)

class _DummyChannel:
    def get_busy(self):
        return False

class _DummySound:
    def __init__(self, array):
        self.array = array

    def play(self, loops=0):
        return _DummyChannel()

pygame_stub.mixer = types.SimpleNamespace(pre_init=lambda *a, **k: None, init=lambda *a, **k: None, Channel=_DummyChannel)
pygame_stub.sndarray = types.SimpleNamespace(make_sound=lambda array: _DummySound(array))

sys.modules.setdefault("pygame", pygame_stub)
sys.modules.setdefault("pygame.sndarray", pygame_stub.sndarray)

from audio import SFX
from config import WIDTH, HEIGHT


class SFXTests(unittest.TestCase):
    def setUp(self):
        self.sfx = SFX(enable_audio=False)

    def test_catalog_defaults_and_variants(self):
        spec = self.sfx.catalog.get_spec("pickup_score_boost")
        self.assertEqual(spec.bus, "sfx")
        self.assertFalse(spec.loop)
        self.assertAlmostEqual(spec.base_gain, 0.9, places=3)
        hit = self.sfx.catalog.get_spec("hit")
        seq = [hit.next_recipe_id() for _ in range(3)]
        self.assertEqual(seq[0], "hit_short")
        self.assertEqual(seq[1], "hit_alt")
        self.assertEqual(seq[2], "hit_short")

    def test_cooldown_blocks_spam(self):
        bus = self.sfx._buses["sfx"]
        self.sfx.play("hit")
        initial = len(bus.voices)
        self.sfx.play("hit")
        self.assertEqual(len(bus.voices), initial)

    def test_ducking_resets_after_window(self):
        self.sfx._now = lambda: 0.0
        self.sfx.duck("loops", gain_db=-6.0, ms=10)
        self.assertLess(self.sfx._buses["loops"].duck_gain, 1.0)
        self.sfx._now = lambda: 0.05
        self.sfx.update(0.02)
        self.assertAlmostEqual(self.sfx._buses["loops"].duck_gain, 1.0, places=5)

    def test_voice_cap_prefers_priority(self):
        bus = self.sfx._buses["sfx"]
        for _ in range(bus.cap):
            self.sfx.play("hit")
            self.sfx._event_last_play["hit"] = self.sfx._now() - 1.0
        self.sfx.play("player_death")
        events = [v.event for v in bus.voices]
        self.assertEqual(len(bus.voices), bus.cap)
        self.assertIn("player_death", events)

    def test_equal_power_panning(self):
        buffer = np.ones((10, 2), dtype=np.float32)
        centred = self.sfx._apply_pan(buffer.copy(), True, (WIDTH / 2, HEIGHT / 2), (WIDTH, HEIGHT))
        self.assertTrue(np.allclose(centred[:, 0], centred[:, 1], atol=1e-5))
        right = self.sfx._apply_pan(buffer.copy(), True, (WIDTH, HEIGHT / 2), (WIDTH, HEIGHT))
        self.assertGreater(right[:, 1].mean(), right[:, 0].mean())

    def test_renderer_headroom_normalised(self):
        result = self.sfx.renderer.render("hit_short")
        peak = float(np.max(np.abs(result.buffer)))
        target = 10 ** (-6.0 / 20.0)
        self.assertLessEqual(peak, target + 1e-3)


if __name__ == "__main__":
    unittest.main()
