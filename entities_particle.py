# entities_particle.py

import random
import math
import time
import numpy as np
import pygame

class Particle:
    def __init__(self, pos, direction=None, cone_angle=None):
        self.pos = np.array(pos, dtype=float)
        if direction is not None and cone_angle is not None:
            half = math.radians(cone_angle) / 2
            angle = random.uniform(direction - half, direction + half)
        else:
            angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(50, 150)
        self.vel = np.array([math.cos(angle) * speed,
                             math.sin(angle) * speed], dtype=float)
        self.radius = random.randint(2, 5)
        self.life = random.uniform(1, 2)
        self.birth = time.time()
        self.color = (
            random.randint(100, 255),
            random.randint(100, 255),
            random.randint(100, 255)
        )

    def update(self, dt):
        self.pos += self.vel * dt
        self.life -= dt

    def draw(self, surf):
        if self.life > 0:
            pygame.draw.circle(
                surf,
                self.color,
                (int(self.pos[0]), int(self.pos[1])),
                self.radius
            )
