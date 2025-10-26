import unittest
from unittest.mock import Mock, patch

import pygame

import sound_manager
from sound_manager import SoundManager


class SoundManagerTests(unittest.TestCase):
    def test_init_failure_disables_sound(self):
        fake_pygame = Mock()
        fake_pygame.error = RuntimeError
        fake_pygame.mixer.get_init.return_value = False
        fake_pygame.mixer.init.side_effect = RuntimeError("boom")
        fake_pygame.sndarray.make_sound = Mock()

        with patch.object(sound_manager, "pygame", fake_pygame):
            manager = SoundManager()

        self.assertFalse(manager.enabled)
        self.assertEqual(manager.sounds, {})

        # Should be a no-op even when sound is missing
        manager.play("explosion")
        manager.loop("player_fire")
        manager.stop("player_fire")

    def test_sound_bank_populated_when_mixer_available(self):
        fake_channel = Mock()
        fake_channel.get_busy.return_value = True
        fake_channel.stop = Mock()

        def make_sound_stub(_array):
            sound = Mock()
            sound.set_volume = Mock()
            sound.play = Mock(return_value=fake_channel)
            return sound

        fake_pygame = Mock()
        fake_pygame.error = RuntimeError
        fake_pygame.mixer.get_init.return_value = True
        fake_pygame.mixer.init = Mock()
        fake_pygame.sndarray.make_sound.side_effect = make_sound_stub

        with patch.object(sound_manager, "pygame", fake_pygame):
            manager = SoundManager()

        fake_pygame.mixer.init.assert_not_called()

        expected_keys = {
            "explosion",
            "player_fire",
            "special_activate",
            "pickup_refuel",
            "pickup_immunity",
            "pickup_tail_boost",
            "pickup_shield",
            "pickup_slow_motion",
            "pickup_score_multiplier",
            "pickup_magnet",
            "pickup_score_boost",
            "pickup_special",
        }

        self.assertTrue(expected_keys.issubset(set(manager.sounds.keys())))

        manager.play("explosion")
        manager.loop("player_fire")
        manager.stop("player_fire")
        fake_channel.stop.assert_called_once()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
