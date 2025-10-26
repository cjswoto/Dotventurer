# entities_obstacles.py

import pygame
import random
import math
import numpy as np
from config import WIDTH, HEIGHT
from entities_utils import irregular_polygon, star_polygon

class Obstacle:
    def __init__(self, level, player_pos=None):
        self.radius = random.randint(10, 30)
        self.color = (
            random.randint(50, 200),
            random.randint(50, 200),
            random.randint(50, 200)
        )
        self.direction = random.uniform(0, 2 * math.pi)
        self.speed = random.uniform(50, 120) + level * 5
        self.score_value = 10
        self.explode = True

        if player_pos is not None:
            safe_zone = WIDTH / 8
            while True:
                x = random.randint(int(player_pos[0] - WIDTH), int(player_pos[0] + WIDTH))
                y = random.randint(int(player_pos[1] - HEIGHT), int(player_pos[1] + HEIGHT))
                pos = np.array([x, y], dtype=float)
                if np.linalg.norm(pos - player_pos) >= safe_zone:
                    break
            self.pos = pos
        else:
            self.pos = np.array([
                random.randint(0, WIDTH),
                random.randint(0, HEIGHT)
            ], dtype=float)

    def update(self, dt, player_pos=None):
        dx = math.cos(self.direction) * self.speed * dt
        dy = math.sin(self.direction) * self.speed * dt
        self.pos[0] += dx
        self.pos[1] += dy

        min_x, max_x = self.radius, WIDTH - self.radius
        min_y, max_y = self.radius, HEIGHT - self.radius

        if self.pos[0] < min_x or self.pos[0] > max_x:
            self.pos[0] = max(min_x, min(self.pos[0], max_x))
            self.direction = math.pi - self.direction
        if self.pos[1] < min_y or self.pos[1] > max_y:
            self.pos[1] = max(min_y, min(self.pos[1], max_y))
            self.direction = -self.direction

    def draw(self, surf):
        pts = irregular_polygon(
            (self.pos[0], self.pos[1]),
            self.radius,
            num_sides=8,
            variation=0.4
        )
        pygame.draw.polygon(surf, self.color, pts)

class ChaserObstacle(Obstacle):
    def __init__(self, level, player_pos):
        super().__init__(level, player_pos)
        self.speed *= 0.7
        self.score_value = 20
        self.rotation = 0

    def update(self, dt, player_pos):
        if player_pos is not None:
            target_angle = math.atan2(
                player_pos[1] - self.pos[1],
                player_pos[0] - self.pos[0]
            )
            self.direction = (self.direction + target_angle) / 2.0
        self.rotation += 0.1 * dt
        super().update(dt, player_pos)

    def draw(self, surf):
        pts = star_polygon(
            (self.pos[0], self.pos[1]),
            outer_radius=self.radius,
            inner_radius=self.radius / 2,
            spikes=5,
            rotation=self.rotation
        )
        pygame.draw.polygon(surf, self.color, pts)

class SplitterObstacle(Obstacle):
    def __init__(self, level, player_pos=None):
        super().__init__(level, player_pos)
        self.radius = random.randint(20, 30)
        self.speed *= 0.8
        self.score_value = 30

    def split(self):
        child1 = Obstacle(1)
        child2 = Obstacle(1)
        child1.radius = max(5, int(self.radius / 2))
        child2.radius = max(5, int(self.radius / 2))
        child1.speed = self.speed * 0.8
        child2.speed = self.speed * 0.8
        child1.score_value = 10
        child2.score_value = 10
        child1.explode = self.explode
        child2.explode = self.explode
        child1.pos = self.pos.copy()
        child2.pos = self.pos.copy()
        return [child1, child2]

    def draw(self, surf):
        pts = irregular_polygon(
            (self.pos[0], self.pos[1]),
            self.radius,
            num_sides=7,
            variation=0.3
        )
        pygame.draw.polygon(surf, self.color, pts)
