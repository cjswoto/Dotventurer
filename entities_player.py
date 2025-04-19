# entities_player.py

import pygame
import numpy as np
from config import ACCELERATION, FRICTION, MIN_THRUST
from entities_utils import regular_polygon

class Player:
    def __init__(self):
        from config import WIDTH, HEIGHT
        self.pos = np.array([WIDTH/2, HEIGHT/2], dtype=float)
        self.vel = np.array([0.0, 0.0], dtype=float)
        self.radius = 12
        self.base_color = (255, 200, 50)
        self.trail = []
        self.fuel = 100
        self.max_fuel = 100
        self.emitting_cooldown = False
        self.cooldown_timer = 0
        self.boosts = []
        self.special_pickup = None
        self.special_active = False
        self.special_timer = 0
        self.immune = False
        self.tail_multiplier = 1
        self.score_multiplier = 1
        self.shield_active = False
        self.magnet_active = False

    def update(self, dt, target):
        """
        Move toward the world-space target position.
        target should be in world coordinates, not clamped to screen.
        """

        # Compute thrust vector toward target
        direction = target - self.pos
        dist = np.linalg.norm(direction)
        if dist > 0:
            thrust = ACCELERATION * min(dist / MIN_THRUST, 1)
            acc = direction / dist * thrust
        else:
            acc = np.zeros_like(self.pos)

        # Apply acceleration and friction
        self.vel += acc * dt
        self.vel *= FRICTION

        # Update position
        self.pos += self.vel * dt

        # Build trail
        self.trail.append((self.pos[0], self.pos[1]))
        max_tail = 50 * self.tail_multiplier
        if len(self.trail) > max_tail:
            self.trail.pop(0)

    def draw(self, surf):
        pts = regular_polygon((self.pos[0], self.pos[1]), self.radius, 8)
        pygame.draw.polygon(surf, self.base_color, pts)
        if len(self.trail) > 1:
            pygame.draw.lines(
                surf,
                (255, 150, 0),
                False,
                [(int(x), int(y)) for x, y in self.trail],
                2
            )
