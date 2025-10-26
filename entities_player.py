# entities_player.py
#
# Full script – replaces the previous version entirely.
# Implements dynamic visuals for active power‑ups plus
# a fuel / cooldown ring around the player icon.
# ------------------------------------------------------

import pygame
import numpy as np
import math
from config import (
    ACCELERATION, FRICTION, MIN_THRUST,
    FUEL_CONSUMPTION_RATE, FUEL_RECHARGE_RATE, COOLDOWN_DURATION,
    WIDTH, HEIGHT
)
from entities_utils import regular_polygon

# ──────────────────────────────────────────────────────────
# Helper utilities
# ──────────────────────────────────────────────────────────
PRIORITY = [
    "immune",          # Immunity pickup
    "shield_active",   # Shield pickup
    "special_ready",   # Has special pickup but not yet used
    "tail_boost",      # Tail boost active
    "magnet_active",   # Magnet pickup
    "score_multiplier",# Score multiplier active
    "slow_motion"      # Slow‑motion active
]

EFFECT_COLORS = {
    "immune":           ( 50, 255,  50),
    "shield_active":    (  0, 191, 255),
    "tail_boost":       (255,   0, 180),
    "magnet_active":    (255,  20, 147),
    "slow_motion":      (138,  43, 226),
    "score_multiplier": (255, 165,   0),
    "special_ready":    (128,   0, 128),
    "base":             (255, 200,  50),
}

def draw_glow(surface, pos, radius, color, alpha=60):
    """Soft radial glow using an SRCALPHA temp surface."""
    temp = pygame.Surface((radius*4, radius*4), pygame.SRCALPHA)
    pygame.draw.circle(temp, (*color, alpha), (radius*2, radius*2), radius*2)
    surface.blit(temp, (pos[0]-radius*2, pos[1]-radius*2))

def lerp(a, b, t):
    return a + (b - a) * t

# ──────────────────────────────────────────────────────────
# Player entity
# ──────────────────────────────────────────────────────────
class Player:
    def __init__(self):
        self.pos   = np.array([WIDTH/2, HEIGHT/2], dtype=float)
        self.vel   = np.array([0.0, 0.0], dtype=float)
        self.radius = 12

        # Core resources
        self.fuel       = 100
        self.max_fuel   = 100
        self.emitting_cooldown = False
        self.cooldown_timer    = 0

        # Gameplay modifiers
        self.trail = []
        self.boosts = []

        # Power‑up flags / timers
        self.immune             = False
        self.tail_multiplier    = 1
        self.score_multiplier   = 1
        self.shield_active      = False
        self.magnet_active      = False
        self.slow_motion_active = False
        self.special_pickup     = None
        self.special_active     = False
        self.special_timer      = 0

        # Base appearance
        self.base_color = EFFECT_COLORS["base"]

    # ──────────────────────────────────────────────────────
    # Movement / physics
    # ──────────────────────────────────────────────────────
    def update(self, dt, target):
        """Move toward world‑space target position."""
        direction = target - self.pos
        dist = np.linalg.norm(direction)
        acc  = (direction / dist * ACCELERATION * min(dist / MIN_THRUST, 1)) if dist > 0 else np.zeros_like(self.pos)

        self.vel += acc * dt
        self.vel *= FRICTION
        self.pos += self.vel * dt

        min_x, max_x = self.radius, WIDTH - self.radius
        min_y, max_y = self.radius, HEIGHT - self.radius

        clamped_x = max(min_x, min(self.pos[0], max_x))
        clamped_y = max(min_y, min(self.pos[1], max_y))

        if clamped_x != self.pos[0]:
            self.pos[0] = clamped_x
            self.vel[0] = 0
        if clamped_y != self.pos[1]:
            self.pos[1] = clamped_y
            self.vel[1] = 0

        # trail build
        self.trail.append(tuple(self.pos))
        max_tail = 50 * self.tail_multiplier
        if len(self.trail) > max_tail:
            self.trail.pop(0)

    # ──────────────────────────────────────────────────────
    # Drawing helpers (power‑up visuals, gauges, etc.)
    # ──────────────────────────────────────────────────────
    def _active_effects(self):
        """Return list of (flag, color) for effects that are on."""
        effects = []
        if self.immune:             effects.append(("immune", EFFECT_COLORS["immune"]))
        if self.shield_active:      effects.append(("shield_active", EFFECT_COLORS["shield_active"]))
        if self.special_pickup:     effects.append(("special_ready", EFFECT_COLORS["special_ready"]))
        if self.tail_multiplier > 1:effects.append(("tail_boost", EFFECT_COLORS["tail_boost"]))
        if self.magnet_active:      effects.append(("magnet_active", EFFECT_COLORS["magnet_active"]))
        if self.slow_motion_active: effects.append(("slow_motion", EFFECT_COLORS["slow_motion"]))
        if self.score_multiplier>1: effects.append(("score_multiplier", EFFECT_COLORS["score_multiplier"]))
        # sort by priority
        effects.sort(key=lambda e: PRIORITY.index(e[0]))
        return effects

    def _draw_fuel_ring(self, surface):
        """Arc ring encodes fuel amount & thickness shows power level."""
        pct = self.fuel / self.max_fuel
        if pct <= 0 and not self.emitting_cooldown:
            return
        center = (int(self.pos[0]), int(self.pos[1]))
        # thickness: 2‑4 px, wider if tail boost (emitter power proxy)
        thick = 3 if self.tail_multiplier == 1 else 5
        radius = self.radius + 6
        start_angle = -math.pi / 2
        end_angle   = start_angle + 2*math.pi * pct
        # color gradient green→yellow→red
        if pct > 0.5:
            color = (lerp(255,255,(pct-0.5)*2), lerp(0,255,(pct-0.5)*2), 0)
        else:
            color = (255, int(255*pct*2), 0)
        pygame.draw.arc(surface, color,
                        (center[0]-radius, center[1]-radius, radius*2, radius*2),
                        start_angle, end_angle, thick)

        # Cooldown overlay clock‑face
        if self.emitting_cooldown:
            t = self.cooldown_timer / COOLDOWN_DURATION  # 1→0
            pygame.draw.arc(surface, (120,120,120),
                            (center[0]-radius-2, center[1]-radius-2, (radius+2)*2, (radius+2)*2),
                            start_angle, start_angle + 2*math.pi*t, thick)

    # ──────────────────────────────────────────────────────
    # Draw
    # ──────────────────────────────────────────────────────
    def draw(self, surf):
        center = (int(self.pos[0]), int(self.pos[1]))
        effects = self._active_effects()
        dominant_color = effects[0][1] if effects else self.base_color

        # Shape selection based on dominant effect
        sides_map = {
            "immune": 0,   # circle
            "shield_active": 3,
            "special_ready": 8,
            "tail_boost": 5,
            "magnet_active": 6,
            "slow_motion": 4,
            "score_multiplier": 10,
        }
        shape_key = effects[0][0] if effects else None
        num_sides = sides_map.get(shape_key, 8)

        # glow (dominant)
        draw_glow(surf, center, self.radius+4, dominant_color, alpha=70)

        # base polygon / circle
        if num_sides == 0:
            pygame.draw.circle(surf, dominant_color, center, self.radius)
        else:
            pts = regular_polygon(center, self.radius, num_sides)
            pygame.draw.polygon(surf, dominant_color, pts)

        # outline rim (for shield or immune)
        if self.immune or self.shield_active:
            rim_color = EFFECT_COLORS["immune"] if self.immune else EFFECT_COLORS["shield_active"]
            pygame.draw.circle(surf, rim_color, center, self.radius+2, 2)

        # magnet horns
        if self.magnet_active:
            angle = pygame.time.get_ticks() * 0.005
            for sign in (-1,1):
                dx = math.cos(angle) * (self.radius+5) * sign
                dy = math.sin(angle) * (self.radius+5)
                pygame.draw.line(surf, EFFECT_COLORS["magnet_active"],
                                 center, (center[0]+dx, center[1]+dy), 2)

        # tail
        if len(self.trail) > 1:
            pygame.draw.lines(
                surf,
                (255, 150, 0),
                False,
                [(int(x), int(y)) for x, y in self.trail],
                2
            )

        # fuel / cooldown ring
        self._draw_fuel_ring(surf)
