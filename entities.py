# entities.py
import pygame
import numpy as np
import random
import math
import time
from config import WIDTH, HEIGHT, WORLD_WIDTH, WORLD_HEIGHT, ACCELERATION

# ----------------------------------------------------------------
# Helper functions for polygon shapes
# ----------------------------------------------------------------
def regular_polygon(center, radius, num_sides, rotation=0):
    cx, cy = center
    points = []
    for i in range(num_sides):
        angle = 2 * math.pi * i / num_sides + rotation
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        points.append((x, y))
    return points

def star_polygon(center, outer_radius, inner_radius, spikes, rotation=0):
    cx, cy = center
    points = []
    for i in range(2 * spikes):
        angle = math.pi * i / spikes + rotation
        r = outer_radius if i % 2 == 0 else inner_radius
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((x, y))
    return points

def irregular_polygon(center, radius, num_sides, variation=0.3, rotation=0):
    cx, cy = center
    points = []
    for i in range(num_sides):
        angle = 2 * math.pi * i / num_sides + rotation
        r = radius * (1 + random.uniform(-variation, variation))
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((x, y))
    return points

# ----------------------------------------------------------------
# Game Objects
# ----------------------------------------------------------------
class Player:
    def __init__(self):
        self.pos = np.array([WIDTH/2, HEIGHT/2], dtype=float)
        self.vel = np.array([0.0, 0.0], dtype=float)
        self.radius = 12
        self.base_color = (255, 200, 50)   # Bright yellow
        self.cooldown_color = (0, 0, 255)    # Blue during cooldown
        self.trail = []
        self.fuel = 100
        self.max_fuel = 100
        self.emitting_cooldown = False
        self.cooldown_timer = 0
        self.boosts = []
        self.special_pickup = None
        self.special_active = False
        self.special_timer = 0
        # New effect attributes:
        self.immune = False
        self.tail_multiplier = 1
        self.score_multiplier = 1
        self.shield_active = False
        self.magnet_active = False

    def update(self, dt, cam_offset):
        target = np.array(cam_offset, dtype=float)
        target[0] = max(0, min(target[0], WIDTH))
        target[1] = max(0, min(target[1], HEIGHT))
        acc = (target - self.pos) * ACCELERATION
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
        max_tail = 50 * self.tail_multiplier
        if len(self.trail) > max_tail:
            self.trail.pop(0)

    def draw(self, surf):
        points = regular_polygon((self.pos[0], self.pos[1]), self.radius, num_sides=8)
        pygame.draw.polygon(surf, self.base_color, points)
        if len(self.trail) > 1:
            pygame.draw.lines(surf, (255, 150, 0), False,
                              [(int(x), int(y)) for x, y in self.trail], 2)

class Obstacle:
    def __init__(self, level, player_pos=None):
        self.radius = random.randint(10, 30)
        self.color = (random.randint(50, 200),
                      random.randint(50, 200),
                      random.randint(50, 200))
        self.direction = random.uniform(0, 2 * math.pi)
        self.speed = random.uniform(50, 120) + level * 5
        self.score_value = 10  # Base score value
        self.explode = True   # Explode on death
        self.emit = False     # Do not auto-emit harmful particles
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
            self.pos = np.array([random.randint(0, WORLD_WIDTH),
                                 random.randint(0, WORLD_HEIGHT)], dtype=float)

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
                self.pos = np.array([random.randint(0, WORLD_WIDTH),
                                     random.randint(0, WORLD_HEIGHT)], dtype=float)
                self.direction = random.uniform(0, 2 * math.pi)

    def draw(self, surf):
        points = irregular_polygon((self.pos[0], self.pos[1]), self.radius, num_sides=8, variation=0.4)
        pygame.draw.polygon(surf, self.color, points)

class ChaserObstacle(Obstacle):
    def __init__(self, level, player_pos):
        super().__init__(level, player_pos)
        self.speed *= 0.7
        self.score_value = 20
        self.rotation = 0
    def update(self, dt, player_pos):
        if player_pos is not None:
            target_direction = math.atan2(player_pos[1] - self.pos[1], player_pos[0] - self.pos[0])
            self.direction = (self.direction + target_direction) / 2.0
        self.rotation += 0.1 * dt
        super().update(dt, player_pos)
    def draw(self, surf):
        points = star_polygon((self.pos[0], self.pos[1]), outer_radius=self.radius, inner_radius=self.radius/2, spikes=5, rotation=self.rotation)
        pygame.draw.polygon(surf, self.color, points)

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
        child1.emit = self.emit
        child2.emit = self.emit
        child1.pos = self.pos.copy()
        child2.pos = self.pos.copy()
        return [child1, child2]
    def draw(self, surf):
        points = irregular_polygon((self.pos[0], self.pos[1]), self.radius, num_sides=7, variation=0.3)
        pygame.draw.polygon(surf, self.color, points)

# ----------------------------------------------------------------
# Particle and Emitter for visual effects/harmful emissions
# ----------------------------------------------------------------
class Particle:
    def __init__(self, pos):
        self.pos = np.array(pos, dtype=float)
        angle = random.uniform(0, 2*math.pi)
        self.vel = np.array([math.cos(angle)*random.uniform(50,150),
                             math.sin(angle)*random.uniform(50,150)], dtype=float)
        self.radius = random.randint(2,5)
        self.life = random.uniform(1,2)
        self.birth = time.time()
        self.color = (random.randint(100,255),
                      random.randint(100,255),
                      random.randint(100,255))
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

# ----------------------------------------------------------------
# Pickups and PowerUps – each rendered as a unique polygon
# ----------------------------------------------------------------
class ExtraFuelPickup:
    def __init__(self):
        self.pos = np.array([random.randint(50, WIDTH-50),
                             random.randint(50, HEIGHT-50)], dtype=float)
        self.radius = 12
        self.color = (0,255,0)
        self.effect = "immunity"  # Grants immunity for 10 sec
        self.duration = 10
    def draw(self, surf):
        points = regular_polygon((self.pos[0], self.pos[1]), self.radius, 4, rotation=math.pi/4)
        pygame.draw.polygon(surf, self.color, points)

class ScoreBoostPickup:
    def __init__(self):
        self.pos = np.array([random.randint(50, WIDTH-50),
                             random.randint(50, HEIGHT-50)], dtype=float)
        self.radius = 12
        self.color = (255,215,0)
    def draw(self, surf):
        points = regular_polygon((self.pos[0], self.pos[1]), self.radius, 4, rotation=math.pi/4)
        pygame.draw.polygon(surf, self.color, points)

class BoostPickup:
    def __init__(self):
        self.pos = np.array([random.randint(50, WIDTH-50),
                             random.randint(50, HEIGHT-50)], dtype=float)
        self.radius = 12
        self.color = (255,105,180)
        self.effect = "tail_boost"  # Doubles tail length for 10 sec and gives a 10% bonus
        self.duration = 10
        self.score_bonus_factor = 0.1
    def draw(self, surf):
        points = regular_polygon((self.pos[0], self.pos[1]), self.radius, 3)
        pygame.draw.polygon(surf, self.color, points)

class SpecialPickup:
    def __init__(self, pos):
        self.pos = np.array(pos, dtype=float)
        self.radius = 15
        self.color = (128,0,128)
    def draw(self, surf):
        points = star_polygon((self.pos[0], self.pos[1]), self.radius, self.radius*0.75, 8)
        pygame.draw.polygon(surf, self.color, points)

class PowerUp:
    def __init__(self):
        self.pos = np.array([random.randint(50, WIDTH-50),
                             random.randint(50, HEIGHT-50)], dtype=float)
        self.base_radius = 12
        self.color = (50,200,50)
    @property
    def radius(self):
        t = pygame.time.get_ticks() / 200.0
        oscillation = 4 * math.sin(t)
        return self.base_radius + abs(oscillation)
    def draw(self, surf):
        points = regular_polygon((self.pos[0], self.pos[1]), self.base_radius, 6)
        pygame.draw.polygon(surf, self.color, points)

# New Pickup classes:
class ShieldPickup:
    def __init__(self):
        self.pos = np.array([random.randint(50, WIDTH-50),
                             random.randint(50, HEIGHT-50)], dtype=float)
        self.radius = 12
        self.color = (0,191,255)
        self.effect = "shield"
        self.duration = 10
    def draw(self, surf):
        rect = (self.pos[0]-self.radius, self.pos[1]-self.radius, 2*self.radius, 2*self.radius)
        pygame.draw.rect(surf, self.color, rect)

class SlowMotionPickup:
    def __init__(self):
        self.pos = np.array([random.randint(50, WIDTH-50),
                             random.randint(50, HEIGHT-50)], dtype=float)
        self.radius = 12
        self.color = (138,43,226)
        self.effect = "slow_motion"
        self.duration = 10
    def draw(self, surf):
        rect = (self.pos[0]-self.radius, self.pos[1]-self.radius/2, 2*self.radius, self.radius)
        pygame.draw.ellipse(surf, self.color, rect)

class ScoreMultiplierPickup:
    def __init__(self):
        self.pos = np.array([random.randint(50, WIDTH-50),
                             random.randint(50, HEIGHT-50)], dtype=float)
        self.radius = 12
        self.color = (255,165,0)
        self.effect = "score_multiplier"
        self.duration = 10
        self.multiplier = 2
    def draw(self, surf):
        points = regular_polygon((self.pos[0], self.pos[1]), self.radius, 5)
        pygame.draw.polygon(surf, self.color, points)

class MagnetPickup:
    def __init__(self):
        self.pos = np.array([random.randint(50, WIDTH-50),
                             random.randint(50, HEIGHT-50)], dtype=float)
        self.radius = 12
        self.color = (255,20,147)
        self.effect = "magnet"
        self.duration = 10
    def draw(self, surf):
        points = regular_polygon((self.pos[0], self.pos[1]), self.radius, 6)
        pygame.draw.polygon(surf, self.color, points)

def check_collision(a, b):
    d = np.linalg.norm(a.pos - b.pos)
    return d < (a.radius + b.radius)
