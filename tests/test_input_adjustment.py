import os
import sys
import types
import unittest


if "pygame" not in sys.modules:
    pygame_stub = types.ModuleType("pygame")

    def _stub_getattr(name):
        return types.SimpleNamespace()

    pygame_stub.__getattr__ = _stub_getattr
    sys.modules["pygame"] = pygame_stub

if "numpy" not in sys.modules:
    numpy_stub = types.ModuleType("numpy")
    numpy_stub.array = lambda value, **_: value
    numpy_stub.zeros_like = lambda value: value
    numpy_stub.linalg = types.SimpleNamespace(norm=lambda _: 0)
    sys.modules["numpy"] = numpy_stub

from game import adjust_mouse_to_viewport


class AdjustMouseToViewportTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("DOTVENTURER_LOG_ENABLED", None)

    def test_returns_original_position_when_no_letterboxing(self):
        self.assertEqual(
            adjust_mouse_to_viewport((100, 200), (1920, 1080)),
            (100, 200),
        )

    def test_applies_letterbox_offset(self):
        self.assertEqual(
            adjust_mouse_to_viewport((60, 70), (2020, 1180)),
            (10, 20),
        )

    def test_clamps_to_viewport_bounds(self):
        self.assertEqual(
            adjust_mouse_to_viewport((5000, -10), (2500, 1300)),
            (1920, 0),
        )


if __name__ == "__main__":
    unittest.main()
