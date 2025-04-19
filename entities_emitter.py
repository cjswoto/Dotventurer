# entities_emitter.py

from config import PARTICLE_RATE, EMITTER_CONE_ANGLE
from entities_particle import Particle

class Emitter:
    def __init__(self, pos):
        self.pos = pos.copy()
        self.particles = []
        self.rate = PARTICLE_RATE
        self.accumulator = 0
        self.max_particles = 100

    def update(self, dt, emitting, cone_direction=None):
        if emitting:
            self.accumulator += dt*self.rate
            while self.accumulator>1:
                if len(self.particles)<self.max_particles:
                    self.particles.append(
                        Particle(self.pos, direction=cone_direction,
                                 cone_angle=EMITTER_CONE_ANGLE)
                    )
                self.accumulator-=1
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.life>0]

    def draw(self, surf):
        for p in self.particles:
            p.draw(surf)
