import os
import unittest

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency in CI
    pygame = None

if pygame is not None:
    from audio import AudioManager
else:  # pragma: no cover - guard for optional dependency
    AudioManager = None

from config import settings_data


@unittest.skipUnless(pygame is not None, "pygame is required for audio tests")
class AudioSettingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.mixer.init()

    @classmethod
    def tearDownClass(cls):
        pygame.mixer.quit()

    def setUp(self):
        settings_data["MUSIC_VOLUME"] = 0.6
        settings_data["SFX_VOLUME"] = 0.7

    def test_settings_include_volume_keys(self):
        self.assertIn("MUSIC_VOLUME", settings_data)
        self.assertIn("SFX_VOLUME", settings_data)

    def test_apply_settings_updates_volumes(self):
        manager = AudioManager()
        settings_data["MUSIC_VOLUME"] = 0.25
        settings_data["SFX_VOLUME"] = 0.75
        manager.apply_settings()
        self.assertAlmostEqual(
            manager.music_sound.get_volume(),
            settings_data["MUSIC_VOLUME"],
            places=2,
        )
        for sound in manager.sfx_sounds.values():
            self.assertAlmostEqual(
                sound.get_volume(),
                settings_data["SFX_VOLUME"],
                places=2,
            )


if __name__ == "__main__":
    unittest.main()
