# entities.py
import pygame
import numpy as np
import random
import math
import time
from config import WIDTH, HEIGHT, WORLD_WIDTH, WORLD_HEIGHT

class Player:
    def __init__(self):
        self.pos = np.array([WIDTH/2, HEIGHT/2], dtype=float)
        self.vel = np.array([0.0, 0.0], dtype=float)
        self.radius = 12
        self.base_color = (255, 200, 50)      # Normal: yellow.
        self.cooldown_color = (0, 0, 255)       # During cooldown: blue.
        self.trail = []
        self.fuel = 100
        self.max_fuel = 100
        self.emitting_cooldown = False
        self.cooldown_timer = 0
        self.boosts = []
        self.special_pickup = None
        self.special_active = False
        self.special_timer = 0

    def update(self, dt, cam_offset):
        # Update the player using a target (computed externally)
        mx, my = pygame.mouse.get_pos()  # (This could be replaced by an externally computed target.)
        target = np.array([mx, my], dtype=float)
        acc = (target - self.pos) * 2.5
        self.vel += acc * dt
        self.vel *= 0.9
        self.pos += self.vel * dt
        if self.pos[0] < self.radius:
            self.pos[0] = self.radius
            self.vel[0] = 0
        if self.pos[1] < self.radius:
            self.pos[1] = self.radius
            self.vel[1] = 0
        self.trail.append(tuple(self.pos))
        if len(self.trail) > 50:
            self.trail.pop(0)

    def draw(self, surf):
        if len(self.trail) > 1:
            pygame.draw.lines(surf, (255, 150, 0), False,
                              [(int(x), int(y)) for x, y in self.trail], 2)
        color = self.cooldown_color if self.emitting_cooldown else self.base_color
        pygame.draw.circle(surf, color, (int(self.pos[0]), int(self.pos[1])), self.radius)

class Obstacle:
    def __init__(self, level, player_pos=None):
        self.radius = random.randint(10, 30)
        self.color = (random.randint(50, 200),
                      random.randint(50, 200),
                      random.randint(50, 200))
        self.direction = random.uniform(0, 2 * math.pi)
        self.speed = random.uniform(50, 120) + level * 5
        self.score_value = 10  # Base obstacle.
        safe_zone = WIDTH / 8
        if player_pos is not None:
            while True:
                x = random.randint(int(player_pos[0] - WIDTH), int(player_pos[0] + WIDTH))
                y = random.randint(int(player_pos[1] - HEIGHT), int(player_pos[1] + HEIGHT))
                pos = np.array([x, y], dtype=float)
                if np.linalg.norm(pos - player_pos) >= safe_zone:
                    break
            self.pos = pos
        else:
            self.pos = np.array([random.randint(0, WORLD_WIDTH), random.randint(0, WORLD_HEIGHT)], dtype=float)

    def update(self, dt, player_pos=None):
        self.pos[0] += math.cos(self.direction) * self.speed * dt
        self.pos[1] += math.sin(self.direction) * self.speed * dt
        if player_pos is not None and (
            self.pos[0] < player_pos[0] - WIDTH or
            self.pos[0] > player_pos[0] + WIDTH or
            self.pos[1] < player_pos[1] - HEIGHT or
            self.pos[1] > player_pos[1] + HEIGHT):
            safe_zone = WIDTH / 8
            while True:
                x = random.randint(int(player_pos[0] - WIDTH), int(player_pos[0] + WIDTH))
                y = random.randint(int(player_pos[1] - HEIGHT), int(player_pos[1] + HEIGHT))
                pos = np.array([x, y], dtype=float)
                if np.linalg.norm(pos - player_pos) >= safe_zone:
                    break
            self.pos = pos
            self.direction = random.uniform(0, 2 * math.pi)
        elif player_pos is None:
            if (self.pos[0] < -self.radius or self.pos[0] > WORLD_WIDTH + self.radius or
                self.pos[1] < -self.radius or self.pos[1] > WORLD_HEIGHT + self.radius):
                self.pos = np.array([random.randint(0, WORLD_WIDTH), random.randint(0, WORLD_HEIGHT)], dtype=float)
                self.direction = random.uniform(0, 2 * math.pi)

    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.pos[0]), int(self.pos[1])), self.radius)

# New Obstacle types.

class ChaserObstacle(Obstacle):
    def __init__(self, level, player_pos):
        super().__init__(level, player_pos)
        self.speed *= 0.7
        self.score_value = 20
    def update(self, dt, player_pos):
        target_direction = math.atan2(player_pos[1] - self.pos[1], player_pos[0] - self.pos[0])
        self.direction = (self.direction + target_direction) / 2.0
        self.pos[0] += math.cos(self.direction) * self.speed * dt
        self.pos[1] += math.sin(self.direction) * self.speed * dt
        if (self.pos[0] < player_pos[0] - WIDTH or
            self.pos[0] > player_pos[0] + WIDTH or
            self.pos[1] < player_pos[1] - HEIGHT or
            self.pos[1] > player_pos[1] + HEIGHT):
            safe_zone = WIDTH / 8
            while True:
                x = random.randint(int(player_pos[0] - WIDTH), int(player_pos[0] + WIDTH))
                y = random.randint(int(player_pos[1] - HEIGHT), int(player_pos[1] + HEIGHT))
                pos = np.array([x, y], dtype=float)
                if np.linalg.norm(pos - player_pos) >= safe_zone:
                    break
            self.pos = pos
            self.direction = target_direction

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
        child1.pos = self.pos.copy()
        child2.pos = self.pos.copy()
        return [child1, child2]

# Particle and Emitter.

class Particle:
    def __init__(self, pos):
        self.pos = np.array(pos, dtype=float)
        angle = random.uniform(0, 2 * math.pi)
        self.vel = np.array([math.cos(angle) * random.uniform(50, 150),
                             math.sin(angle) * random.uniform(50, 150)], dtype=float)
        self.radius = random.randint(2, 5)
        self.life = random.uniform(1, 2)
        self.birth = time.time()
        self.color = (random.randint(100, 255),
                      random.randint(100, 255),
                      random.randint(100, 255))
    def update(self, dt):
        self.pos += self.vel * dt
        self.life -= dt
    def draw(self, surf):
        if self.life > 0:
            pygame.draw.circle(surf, self.color, (int(self.pos[0]), int(self.pos[1])), self.radius)

class Emitter:
    def __init__(self, pos):
        self.pos = np.array(pos, dtype=float)
        self.particles = []
        self.rate = 30
        self.accumulator = 0
        self.max_particles = 100

    def update(self, dt, emitting, cone_direction=None):
        # cone_direction is not used by default.
        if emitting:
            self.accumulator += dt * self.rate
            while self.accumulator > 1:
                if len(self.particles) < self.max_particles:
                    self.particles.append(Particle(self.pos))
                self.accumulator -= 1
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]

    def draw(self, surf):
        for p in self.particles:
            p.draw(surf)

# New Pickup Classes.

class ExtraFuelPickup:
    def __init__(self):
        self.pos = np.array([random.randint(50, WIDTH - 50),
                             random.randint(50, HEIGHT - 50)], dtype=float)
        self.radius = 12
        self.color = (0, 255, 0)  # Bright green.
        self.restore_amount = 15
    def draw(self, surf):
        pygame.draw.rect(surf, self.color, (int(self.pos[0] - self.radius), int(self.pos[1] - self.radius),
                                              self.radius * 2, self.radius * 2))

class ScoreBoostPickup:
    def __init__(self):
        self.pos = np.array([random.randint(50, WIDTH - 50),
                             random.randint(50, HEIGHT - 50)], dtype=float)
        self.radius = 12
        self.color = (255, 215, 0)  # Gold.
    def draw(self, surf):
        points = [
            (self.pos[0], self.pos[1] - self.radius),
            (self.pos[0] + self.radius, self.pos[1]),
            (self.pos[0], self.pos[1] + self.radius),
            (self.pos[0] - self.radius, self.pos[1])
        ]
        pygame.draw.polygon(surf, self.color, points)

class BoostPickup:
    def __init__(self):
        self.pos = np.array([random.randint(50, WIDTH - 50),
                             random.randint(50, HEIGHT - 50)], dtype=float)
        self.radius = 12
        self.color = (255, 105, 180)  # Hot pink.
    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.pos[0]), int(self.pos[1])), self.radius)

class SpecialPickup:
    def __init__(self, pos):
        self.pos = np.array(pos, dtype=float)
        self.radius = 15
        self.color = (128, 0, 128)  # Purple.
    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.pos[0]), int(self.pos[1])), self.radius)

# Standard PowerUp (unchanged functionality from before).
class PowerUp:
    def __init__(self):
        self.pos = np.array([random.randint(50, WIDTH - 50),
                             random.randint(50, HEIGHT - 50)], dtype=float)
        self.base_radius = 12
        self.color = (50, 200, 50)
    @property
    def radius(self):
        t = pygame.time.get_ticks() / 200.0
        oscillation = 4 * math.sin(t)
        return self.base_radius + abs(oscillation)
    def draw(self, surf):
        t = pygame.time.get_ticks() / 200.0
        oscillation = 4 * math.sin(t)
        radius = self.base_radius + oscillation
        points = [
            (self.pos[0], self.pos[1] - radius),
            (self.pos[0] + radius, self.pos[1]),
            (self.pos[0], self.pos[1] + radius),
            (self.pos[0] - radius, self.pos[1])
        ]
        pygame.draw.polygon(surf, self.color, points)

def check_collision(a, b):
    d = np.linalg.norm(a.pos - b.pos)
    return d < (a.radius + b.radius)
