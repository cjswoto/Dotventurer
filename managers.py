# managers.py

import random
import math
import pygame
import time

class Timer:
    def __init__(self, duration):
        self.duration = duration
        self.start = time.time()
    def expired(self):
        return (time.time() - self.start) >= self.duration
    def reset(self):
        self.start = time.time()

class LevelManager:
    def __init__(self):
        self.level = 1
        self.timer = Timer(10)
    def update(self):
        if self.timer.expired():
            self.level += 1
            self.timer.reset()
    def get_level(self):
        return self.level

class Explosion:
    def __init__(self, pos):
        from entities import Particle
        self.particles = [Particle(pos) for _ in range(30)]
        self.done = False
    def update(self, dt):
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]
        if not self.particles:
            self.done = True
    def draw(self, surf):
        for p in self.particles:
            p.draw(surf)

class ExplosionManager:
    def __init__(self, sound_manager=None):
        self.explosions = []
        self.sound_manager = sound_manager
    def add(self, pos):
        self.explosions.append(Explosion(pos))
        if self.sound_manager:
            self.sound_manager.play("explosion")
    def update(self, dt):
        for exp in self.explosions:
            exp.update(dt)
        self.explosions = [e for e in self.explosions if not e.done]
    def draw(self, surf):
        for exp in self.explosions:
            exp.draw(surf)

class Camera:
    def __init__(self):
        self.offset = pygame.math.Vector2(0, 0)
        self.shake_duration = 0
        self.shake_intensity = 0
    def update(self, dt):
        if self.shake_duration > 0:
            self.shake_duration -= dt
            self.offset.x = random.uniform(-self.shake_intensity, self.shake_intensity)
            self.offset.y = random.uniform(-self.shake_intensity, self.shake_intensity)
        else:
            self.offset.x = 0
            self.offset.y = 0
    def shake(self, duration, intensity):
        self.shake_duration = duration
        self.shake_intensity = intensity
