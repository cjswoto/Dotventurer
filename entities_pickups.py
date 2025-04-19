# entities_pickups.py
import random, math, pygame, numpy as np
from config          import WIDTH, HEIGHT
from entities_utils  import regular_polygon, star_polygon

# ------------------------------------------------------------
# Utility: spawn well inside the play‑field
# ------------------------------------------------------------
def _pos():
    return np.array(
        [random.randint(50, WIDTH-50), random.randint(50, HEIGHT-50)],
        dtype=float
    )

# ------------------------------------------------------------
# Base‑class helper for the new glow effect
# ------------------------------------------------------------
def _glow(surface, centre, radius, color, ticks):
    """Draw a faint pulsating ring behind the pickup."""
    pulse = 2 + abs(math.sin(ticks * 0.005)) * 4       # 2‑6 px extra
    glow_r = int(radius + pulse)
    glow_color = (*color, 60)                          # low alpha
    # pygame doesn’t support per‑primitive alpha; use a temp surface
    temp = pygame.Surface((glow_r*2, glow_r*2), pygame.SRCALPHA)
    pygame.draw.circle(temp, glow_color, (glow_r, glow_r), glow_r)
    surface.blit(temp, (centre[0]-glow_r, centre[1]-glow_r))

# ------------------------------------------------------------
# Cosmetic (no timer)
# ------------------------------------------------------------
class PowerUp:
    def __init__(self):
        self.pos, self.base_radius, self.color = _pos(), 12, (50,200,50)
    @property
    def radius(self):
        return self.base_radius + abs(4*math.sin(pygame.time.get_ticks()*0.005))
    def draw(self, surf):
        pts = regular_polygon(self.pos, self.base_radius, 6)
        _glow(surf, self.pos, self.base_radius, self.color, pygame.time.get_ticks())
        pygame.draw.polygon(surf, self.color, pts)

# ------------------------------------------------------------
# Timed pickups (all now 30 s instead of 10 s)
# ------------------------------------------------------------
class ExtraFuelPickup:
    def __init__(self):
        self.pos, self.radius, self.color = _pos(), 12, (0,255,0)
        self.effect, self.duration = "immunity", 30
    def draw(self, surf):
        _glow(surf, self.pos, self.radius, self.color, pygame.time.get_ticks())
        pts = regular_polygon(self.pos, self.radius, 4, rotation=math.pi/4)
        pygame.draw.polygon(surf, self.color, pts)

class BoostPickup:
    def __init__(self):
        self.pos, self.radius, self.color = _pos(), 12, (255,105,180)
        self.effect, self.duration, self.score_bonus_factor = "tail_boost", 30, 0.1
    def draw(self, surf):
        _glow(surf, self.pos, self.radius, self.color, pygame.time.get_ticks())
        pts = regular_polygon(self.pos, self.radius, 3)
        pygame.draw.polygon(surf, self.color, pts)

class ShieldPickup:
    def __init__(self):
        self.pos, self.radius, self.color = _pos(), 12, (0,191,255)
        self.effect, self.duration = "shield", 30
    def draw(self, surf):
        _glow(surf, self.pos, self.radius, self.color, pygame.time.get_ticks())
        rect = (self.pos[0]-self.radius, self.pos[1]-self.radius,
                2*self.radius, 2*self.radius)
        pygame.draw.rect(surf, self.color, rect)

class SlowMotionPickup:
    def __init__(self):
        self.pos, self.radius, self.color = _pos(), 12, (138,43,226)
        self.effect, self.duration = "slow_motion", 30
    def draw(self, surf):
        _glow(surf, self.pos, self.radius, self.color, pygame.time.get_ticks())
        rect = (self.pos[0]-self.radius, self.pos[1]-self.radius/2,
                2*self.radius, self.radius)
        pygame.draw.ellipse(surf, self.color, rect)

class ScoreMultiplierPickup:
    def __init__(self):
        self.pos, self.radius, self.color = _pos(), 12, (255,165,0)
        self.effect, self.duration, self.multiplier = "score_multiplier", 30, 2
    def draw(self, surf):
        _glow(surf, self.pos, self.radius, self.color, pygame.time.get_ticks())
        pts = regular_polygon(self.pos, self.radius, 5)
        pygame.draw.polygon(surf, self.color, pts)

class MagnetPickup:
    def __init__(self):
        self.pos, self.radius, self.color = _pos(), 12, (255,20,147)
        self.effect, self.duration = "magnet", 30
    def draw(self, surf):
        _glow(surf, self.pos, self.radius, self.color, pygame.time.get_ticks())
        pts = regular_polygon(self.pos, self.radius, 6)
        pygame.draw.polygon(surf, self.color, pts)

# ------------------------------------------------------------
# ScoreBoostPickup (instant score) and SpecialPickup (special)
# keep their original behaviour but get the glow for consistency
# ------------------------------------------------------------
class ScoreBoostPickup:
    def __init__(self):
        self.pos, self.radius, self.color = _pos(), 12, (255,215,0)
    def draw(self, surf):
        _glow(surf, self.pos, self.radius, self.color, pygame.time.get_ticks())
        pts = regular_polygon(self.pos, self.radius, 4, rotation=math.pi/4)
        pygame.draw.polygon(surf, self.color, pts)

class SpecialPickup:
    def __init__(self, pos):
        self.pos, self.radius, self.color = np.array(pos,float), 15, (128,0,128)
    def draw(self, surf):
        _glow(surf, self.pos, self.radius, self.color, pygame.time.get_ticks())
        pts = star_polygon(self.pos, self.radius, self.radius*0.75, 8)
        pygame.draw.polygon(surf, self.color, pts)
