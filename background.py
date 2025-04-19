# background.py

import pygame
import random
from config import WIDTH, HEIGHT

class Background:
    def __init__(self):
        # Example starfield background
        self.stars = [(random.randint(0, WIDTH), random.randint(0, HEIGHT)) for _ in range(100)]

    def update(self, dt):
        # Simple twinkle/movement: jitter each star
        new_stars = []
        for x, y in self.stars:
            nx = (x + random.randint(-1, 1)) % WIDTH
            ny = (y + random.randint(-1, 1)) % HEIGHT
            new_stars.append((nx, ny))
        self.stars = new_stars

    def draw(self, surf):
        surf.fill((0, 0, 0))  # Solid black
        for x, y in self.stars:
            pygame.draw.circle(surf, (255, 255, 255), (x, y), 1)
