import sys
import types
import unittest


pygame_stub = sys.modules.get("pygame")
if pygame_stub is None:
    pygame_stub = types.ModuleType("pygame")
    sys.modules["pygame"] = pygame_stub

if not hasattr(pygame_stub, "error"):
    pygame_stub.error = Exception

if not hasattr(pygame_stub, "mixer"):
    pygame_stub._mixer_initialized = False

    def _get_init():
        return pygame_stub._mixer_initialized

    def _init(**kwargs):
        pygame_stub._mixer_initialized = True

    pygame_stub.mixer = types.SimpleNamespace(
        get_init=_get_init,
        init=_init,
    )

if not hasattr(pygame_stub, "sndarray"):
    class _Sound:
        def play(self, *args, **kwargs):
            return None

        def stop(self):
            return None

    pygame_stub.sndarray = types.SimpleNamespace(
        make_sound=lambda *args, **kwargs: _Sound()
    )

from sound_manager import SoundLibrary


class SoundLibraryTests(unittest.TestCase):
    def setUp(self):
        self.library = SoundLibrary()

    def test_expected_keys_present(self):
        expected = {
            "explosion",
            "special_activate",
            "attack_emit",
            "attack_hit",
            "pickup_powerup",
            "pickup_immunity",
            "pickup_tail_boost",
            "pickup_shield",
            "pickup_slow_motion",
            "pickup_score_multiplier",
            "pickup_magnet",
            "pickup_score_boost",
            "pickup_special",
        }
        self.assertTrue(expected.issubset(self.library.sounds.keys()))

    def test_play_controls_do_not_raise(self):
        self.library.play("explosion")
        self.library.loop("attack_emit")
        self.library.stop("attack_emit")
        # Unknown keys should be ignored silently
        self.library.play("unknown")


if __name__ == "__main__":
    unittest.main()
