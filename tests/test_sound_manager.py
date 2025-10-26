from sound_manager import SoundManager


def test_sound_manager_has_expected_sounds():
    manager = SoundManager(enable_audio=False)
    expected = {
        "explosion",
        "pickup_refuel",
        "pickup_immunity",
        "pickup_tail_boost",
        "pickup_shield",
        "pickup_slow_motion",
        "pickup_score_multiplier",
        "pickup_magnet",
        "pickup_score_boost",
        "pickup_special",
        "player_attack",
        "player_attack_hit",
        "special_activate",
    }
    assert expected.issubset(manager.sound_specs.keys())
    pickup_freqs = [
        manager.sound_specs[key].frequency for key in expected if key.startswith("pickup_")
    ]
    assert len(pickup_freqs) == len(set(pickup_freqs))


def test_sound_manager_methods_no_audio():
    manager = SoundManager(enable_audio=False)
    assert manager.enabled is False
    manager.play("explosion")
    manager.play_loop("player_attack")
    manager.stop_loop("player_attack")
    manager.stop_all()
