# background.py
import pygame

class Background:
    def __init__(self):
        # No pre-rendered cache is needed when the background is disabled.
        pass

    def update(self, dt):
        # Background animation/update disabled.
        pass

    def draw(self, surf):
        # Instead of drawing a grid, fill the entire surface with a plain color (black).
        surf.fill((0, 0, 0))
