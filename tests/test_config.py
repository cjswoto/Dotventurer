import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config import (
    SOUND_MUSIC_VOLUME,
    SOUND_SFX_VOLUME,
    settings_data,
)


class SoundSettingsTestCase(unittest.TestCase):
    def test_sound_volume_defaults_present(self):
        self.assertIn("SOUND_MUSIC_VOLUME", settings_data)
        self.assertIn("SOUND_SFX_VOLUME", settings_data)

    def test_sound_volume_defaults_range(self):
        music = settings_data["SOUND_MUSIC_VOLUME"]
        sfx = settings_data["SOUND_SFX_VOLUME"]
        for value in (music, sfx):
            with self.subTest(value=value):
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)

    def test_sound_volume_defaults_match_constants(self):
        self.assertEqual(settings_data["SOUND_MUSIC_VOLUME"], SOUND_MUSIC_VOLUME)
        self.assertEqual(settings_data["SOUND_SFX_VOLUME"], SOUND_SFX_VOLUME)


if __name__ == "__main__":
    unittest.main()
