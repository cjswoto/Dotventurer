import os

import pygame

from sound_manager import SoundManager
from entities_pickups import ImmunityPickup, ScoreBoostPickup


def setup_module(module):
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    if not hasattr(pygame, "get_init"):
        pygame.get_init = lambda: True
    if not hasattr(pygame, "init"):
        pygame.init = lambda: None
    if not pygame.get_init():
        pygame.init()


def test_sound_manager_pickup_event(monkeypatch):
    monkeypatch.setattr(SoundManager, "_init_mixer", lambda self: False)
    manager = SoundManager()
    captured = []
    monkeypatch.setattr(SoundManager, "play", lambda self, event: captured.append(event))

    manager.play_for_pickup(ImmunityPickup())
    assert captured[-1] == "pickup_immunity"

    manager.play_for_pickup(ScoreBoostPickup())
    assert captured[-1] == "pickup_ScoreBoostPickup"


def test_sound_manager_unknown_pickup(monkeypatch):
    class DummyPickup:
        pass

    monkeypatch.setattr(SoundManager, "_init_mixer", lambda self: False)
    manager = SoundManager()
    captured = []
    monkeypatch.setattr(SoundManager, "play", lambda self, event: captured.append(event))

    manager.play_for_pickup(DummyPickup())
    assert captured[-1] == "pickup_powerup"
