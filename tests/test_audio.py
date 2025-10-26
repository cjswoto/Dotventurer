import sys
import types
import unittest
from unittest import mock

if "pygame" not in sys.modules:
    pygame_stub = types.ModuleType("pygame")

    class _DummyChannel:
        def __init__(self, index):
            self.index = index
            self._busy = False

        def get_busy(self):
            return self._busy

        def set_volume(self, left, right):
            pass

        def play(self, sound, loops=0):
            self._busy = loops == -1

        def stop(self):
            self._busy = False

    pygame_stub.mixer = types.SimpleNamespace(
        init=lambda **kwargs: None,
        get_init=lambda: False,
        set_num_channels=lambda n: None,
        Channel=lambda index: _DummyChannel(index),
    )
    pygame_stub.sndarray = types.SimpleNamespace(make_sound=lambda data: data)
    sys.modules["pygame"] = pygame_stub

from audio.catalog import SFXCatalog
from audio.sfx import SFX


class CatalogTests(unittest.TestCase):
    def test_variant_rotation(self):
        catalog = SFXCatalog("assets/sfx_catalog.json")
        first = catalog.next_recipe_id("hit")
        second = catalog.next_recipe_id("hit")
        self.assertNotEqual(first, second)
        spec = catalog.get_spec("hit")
        self.assertEqual(spec.recipe_ids[0], first)
        self.assertEqual(spec.recipe_ids[1], second)


class SFXLogicTests(unittest.TestCase):
    def test_cooldown_and_voice_steal(self):
        times = [0.0, 0.01]
        times.extend(0.2 + 0.1 * i for i in range(40))
        time_iter = iter(times)

        def fake_time():
            return next(time_iter)

        with mock.patch("audio.sfx.time.monotonic", side_effect=fake_time):
            sfx = SFX(enable_audio=False)
            self.assertTrue(sfx.play("hit"))
            self.assertFalse(sfx.play("hit"))  # cooldown merges immediate repeat
            self.assertTrue(sfx.play("hit"))
            for _ in range(14):
                self.assertTrue(sfx.play("hit"))
            bus = sfx._buses["sfx"]
            self.assertEqual(len(bus.voices), 16)
            self.assertFalse(sfx.play("pickup_score_boost"))  # lower priority rejected
            self.assertEqual(len(bus.voices), 16)
            self.assertTrue(sfx.play("explosion"))  # higher priority steals
            self.assertEqual(len(bus.voices), 16)
            self.assertTrue(any(voice.event == "explosion" for voice in bus.voices))


if __name__ == "__main__":
    unittest.main()
