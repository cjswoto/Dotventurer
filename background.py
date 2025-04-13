# background.py
import pygame
import random
import numpy as np
from config import WIDTH, HEIGHT

class Background:
    def __init__(self):
        # Example starfield background
        self.stars = [(random.randint(0, WIDTH), random.randint(0, HEIGHT)) for _ in range(100)]

    def update(self, dt):
        # If you want twinkling or movement logic, place it here
        pass

    def draw(self, surf):
        surf.fill((0, 0, 0))  # Solid black background
        for (x, y) in self.stars:
            pygame.draw.circle(surf, (255, 255, 255), (x, y), 1)
