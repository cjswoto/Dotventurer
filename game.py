# game.py
# ──────────────────────────────────────────────────────────────
# Complete script – April 18 2025 build C (frames removed)
# ──────────────────────────────────────────────────────────────

import pygame
import numpy as np
import random
import time
import sys
import json
import math

from config import (
    WIDTH, HEIGHT,
    settings_data, FUEL_CONSUMPTION_RATE,
    FUEL_RECHARGE_RATE, COOLDOWN_DURATION
)
from entities import (
    Player, Obstacle, PowerUp, ExtraFuelPickup,
    ScoreBoostPickup, BoostPickup, SpecialPickup,
    ShieldPickup, SlowMotionPickup, ScoreMultiplierPickup,
    MagnetPickup, check_collision, ChaserObstacle,
    SplitterObstacle, Emitter
)
from entities_utils import regular_polygon
from background import Background
from managers import LevelManager, ExplosionManager, Camera, Timer
from ui import Button, Leaderboard


def clamp(v, lo, hi):
    return max(lo, min(v, hi))


# ──────────────────────────────────────────────────────────────
# Small helper – 20 px pickup icon (no surrounding frame)
# ──────────────────────────────────────────────────────────────
def draw_powerup_icon(surface, pos, effect):
    x, y = pos
    r = 10
    if effect == "immunity":            sides, col, rot = 4, (0, 255,   0),  math.pi/4
    elif effect == "shield":            sides, col, rot = 4, (0, 191, 255),  0
    elif effect == "tail_boost":        sides, col, rot = 3, (255,105,180),  0
    elif effect == "magnet":            sides, col, rot = 6, (255, 20,147),  0
    elif effect == "slow_motion":       sides, col, rot = 4, (138, 43,226),  0
    elif effect == "score_multiplier":  sides, col, rot = 5, (255,165,  0),  0
    else:                               sides, col, rot = 8, (255,255,255),  0

    if effect == "slow_motion":
        rect = (x - r, y - r / 2, r * 2, r)
        pygame.draw.ellipse(surface, col, rect)
    else:
        pts = regular_polygon((x, y), r, sides, rot)
        pygame.draw.polygon(surface, col, pts)


# ──────────────────────────────────────────────────────────────
# Main Game class
# ──────────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        pygame.init()
        info = pygame.display.Info()
        self.window = pygame.display.set_mode((info.current_w, info.current_h))
        self.clock = pygame.time.Clock()

        # core state
        self.state = "menu"
        self.player = Player()
        self.level_manager = LevelManager()

        # world objects / managers
        self.obstacles = [self.spawn_obstacle() for _ in range(5)]
        self.emitter = Emitter(self.player.pos)
        self.power_timer = Timer(7)
        self.background = Background()
        self.explosion_manager = ExplosionManager()
        self.camera = Camera()
        self.leaderboard = Leaderboard()

        # misc gameplay data
        self.powerups = []
        self.flash_messages = []
        self.camera_pos = self.player.pos.copy()
        self.score = 0
        self.slow_multiplier = 1

        # UI buttons
        self.menu_buttons = [
            Button((WIDTH/2-100, HEIGHT/2-100, 200, 50), "Start Game", 30),
            Button((WIDTH/2-100, HEIGHT/2-40,  200, 50), "Settings",   30),
            Button((WIDTH/2-100, HEIGHT/2+20, 200, 50), "Score Board", 30),
            Button((WIDTH/2-100, HEIGHT/2+80, 200, 50), "About",       30),
            Button((WIDTH/2-100, HEIGHT/2+140,200, 50), "Exit",        30)
        ]
        self.settings_keys  = ["FPS","FUEL_CONSUMPTION_RATE","FUEL_RECHARGE_RATE","COOLDOWN_DURATION"]
        self.settings_steps = {"FPS":5,"FUEL_CONSUMPTION_RATE":5,"FUEL_RECHARGE_RATE":0.1,"COOLDOWN_DURATION":0.5}
        self.settings_back_button = Button((WIDTH/2-50, HEIGHT-80, 100, 40), "Back", 30)
        self.back_button    = Button((WIDTH/2-50, HEIGHT-80, 100, 40), "Back", 30)
        self.restart_button = Button((WIDTH/2-100,HEIGHT/2+50, 200, 50), "Restart", 30)

        self.about_data = self._load_about()

    # ──────────────────────────────────────────────────────
    # Utility loaders
    def _load_about(self):
        try:
            with open("about.json", "r") as f:
                return json.load(f)
        except Exception:
            return {"title": "About", "objects": [], "instructions": ["No about data available."]}

    # ──────────────────────────────────────────────────────
    # Spawning helpers
    def spawn_obstacle(self):
        kind = random.choice(["base", "chaser", "splitter"])
        lvl  = self.level_manager.get_level()
        obs  = ChaserObstacle(lvl, self.player.pos) if kind == "chaser" else \
               SplitterObstacle(lvl, self.player.pos) if kind == "splitter" else \
               Obstacle(lvl, player_pos=self.player.pos)
        obs.pos = np.array([random.randint(0, WIDTH), random.randint(0, HEIGHT)], dtype=float)
        return obs

    def reset(self):
        self.player = Player()
        self.level_manager = LevelManager()
        self.obstacles = [self.spawn_obstacle() for _ in range(5)]
        self.emitter = Emitter(self.player.pos)
        self.powerups = []
        self.power_timer.reset()
        self.score = 0
        self.explosion_manager = ExplosionManager()
        self.camera = Camera()
        self.camera_pos = self.player.pos.copy()
        self.flash_messages = []
        self.slow_multiplier = 1

    # ──────────────────────────────────────────────────────
    # Event handling
    def handle_event(self, event, adj_mouse):
        pos = adj_mouse if adj_mouse is not None else pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.state == "menu":
                for b in self.menu_buttons:
                    if b.is_hovered(pos):
                        if   b.text == "Start Game":    self.reset(); self.state = "playing"
                        elif b.text == "Settings":      self.state = "settings"
                        elif b.text == "Score Board":   self.state = "scoreboard"
                        elif b.text == "About":         self.state = "about"
                        elif b.text == "Exit":          pygame.quit(); sys.exit()

            elif self.state == "settings":
                for i, key in enumerate(self.settings_keys):
                    y = 100 + i * 60
                    minus = pygame.Rect(WIDTH/2+50, y, 30, 30)
                    plus  = pygame.Rect(WIDTH/2+90, y, 30, 30)
                    if minus.collidepoint(pos):
                        settings_data[key] = clamp(settings_data[key] - self.settings_steps[key], 0, 1e9)
                    elif plus.collidepoint(pos):
                        settings_data[key] += self.settings_steps[key]
                if self.settings_back_button.is_hovered(pos):
                    self.state = "menu"

            elif self.state in ("scoreboard", "about"):
                if self.back_button.is_hovered(pos):
                    self.state = "menu"

            elif self.state == "gameover":
                if self.restart_button.is_hovered(pos):
                    self.leaderboard.add_score(self.score)
                    self.reset(); self.state = "playing"

            # Right‑click special ability
            if event.button == 3 and self.state == "playing" and self.player.special_pickup:
                self._activate_special()

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and self.state == "playing":
                self.state = "menu"
            elif self.state == "menu" and event.key == pygame.K_SPACE:
                self.reset(); self.state = "playing"
            elif self.state == "gameover" and event.key == pygame.K_r:
                self.leaderboard.add_score(self.score)
                self.reset(); self.state = "playing"

    # ──────────────────────────────────────────────────────
    # Gameplay helpers
    def _activate_special(self):
        bonus = sum(o.score_value for o in self.obstacles)
        for o in self.obstacles:
            self.explosion_manager.add(o.pos.copy())
        self.obstacles.clear()
        self.score += bonus
        self.player.special_active = True
        self.player.special_timer  = 3
        self.player.special_pickup = None

    def _expire_effects(self, now):
        if self.player.immune and now > getattr(self.player, "immune_timer", 0):
            self.player.immune = False
        if getattr(self.player, "tail_boost_timer", 0) and now > self.player.tail_boost_timer:
            self.player.tail_multiplier = 1
        if getattr(self.player, "score_multiplier_timer", 0) and now > self.player.score_multiplier_timer:
            self.player.score_multiplier = 1
        if self.player.shield_active and now > getattr(self.player, "shield_timer", 0):
            self.player.shield_active = False
        if getattr(self, "slow_timer", 0) and now > self.slow_timer:
            self.slow_multiplier = 1
            self.player.slow_motion_active = False
        if self.player.magnet_active and now > getattr(self.player, "magnet_timer", 0):
            self.player.magnet_active = False

    # ──────────────────────────────────────────────────────
    # Update loop
    def update(self, dt):
        if self.state != "playing":
            self.flash_messages = [f for f in self.flash_messages if time.time() < f["timer"]]
            return

        now = time.time()
        self._expire_effects(now)

        # Player movement
        mx, my = pygame.mouse.get_pos()
        w, h = self.window.get_size()
        x_off, y_off = (w - WIDTH) // 2, (h - HEIGHT) // 2
        mx, my = clamp(mx - x_off, 0, WIDTH), clamp(my - y_off, 0, HEIGHT)
        world_mouse = self.camera_pos + np.array([mx - WIDTH/2, my - HEIGHT/2])
        self.player.update(dt, world_mouse)

        # Camera follow with dead‑zone
        margin_x, margin_y = WIDTH / 8, HEIGHT / 8
        center = np.array([WIDTH/2, HEIGHT/2])
        p_screen = self.player.pos - (self.camera_pos - center)
        if p_screen[0] < margin_x:               self.camera_pos[0] = self.player.pos[0] - margin_x + center[0]
        elif p_screen[0] > WIDTH - margin_x:     self.camera_pos[0] = self.player.pos[0] - (WIDTH - margin_x) + center[0]
        if p_screen[1] < margin_y:               self.camera_pos[1] = self.player.pos[1] - margin_y + center[1]
        elif p_screen[1] > HEIGHT - margin_y:    self.camera_pos[1] = self.player.pos[1] - (HEIGHT - margin_y) + center[1]

        # Fuel / emitter
        left_down = pygame.mouse.get_pressed()[0]
        emitting = False
        if left_down and not self.player.emitting_cooldown and self.player.fuel > 0:
            self.player.fuel -= FUEL_CONSUMPTION_RATE * dt
            if self.player.fuel <= 0:
                self.player.fuel = 0
                self.player.emitting_cooldown = True
                self.player.cooldown_timer = COOLDOWN_DURATION
            emitting = True

        recharge = FUEL_RECHARGE_RATE * (1 + 0.1 * len(self.player.boosts))
        self.player.fuel = min(self.player.max_fuel, self.player.fuel + recharge * dt)
        if self.player.emitting_cooldown:
            self.player.cooldown_timer -= dt
            if self.player.cooldown_timer <= 0:
                self.player.emitting_cooldown = False

        self.emitter.pos = self.player.pos.copy()
        self.emitter.update(dt, emitting)

        # Obstacle movement
        for o in self.obstacles:
            o.update(dt * self.slow_multiplier, self.player.pos)

        # Player vs obstacle
        for o in self.obstacles[:]:
            if check_collision(self.player, o):
                if self.player.immune:
                    continue
                if self.player.shield_active:
                    self.player.shield_active = False
                    self.explosion_manager.add(o.pos.copy())
                    if hasattr(o, "split"): self.obstacles.extend(o.split())
                    self.obstacles.remove(o)
                    continue
                self.explosion_manager.add(self.player.pos.copy())
                self.camera.shake(0.5, 15)
                self.state = "gameover"
                return

        # Particles vs obstacle
        for o in self.obstacles[:]:
            for p in self.emitter.particles[:]:
                if check_collision(p, o):
                    self.score += o.score_value
                    self.flash_messages.append({"text": str(o.score_value), "timer": now + 1.5,
                                                "pos": (int(o.pos[0]), int(o.pos[1])), "font_size": 25})
                    if o.explode: self.explosion_manager.add(o.pos.copy())
                    if hasattr(o, "split"): self.obstacles.extend(o.split())
                    self.obstacles.remove(o)
                    if p in self.emitter.particles:
                        self.emitter.particles.remove(p)
                    break

        # Trail vs obstacle
        for o in self.obstacles[:]:
            for pt in self.player.trail[::5]:
                if np.linalg.norm(np.array(pt) - o.pos) < o.radius:
                    self.score += 25
                    if o.explode: self.explosion_manager.add(o.pos.copy())
                    if hasattr(o, "split"): self.obstacles.extend(o.split())
                    self.obstacles.remove(o)
                    break

        # Spawn new pickups
        if self.power_timer.expired():
            new_pick = random.choice([
                PowerUp, ExtraFuelPickup, ScoreBoostPickup, BoostPickup,
                lambda: SpecialPickup(self.player.pos.copy()),
                ShieldPickup, SlowMotionPickup, ScoreMultiplierPickup, MagnetPickup
            ])()
            self.powerups.append(new_pick)
            self.power_timer.reset()

        # Pickup collisions
        for pu in self.powerups[:]:
            if check_collision(self.player, pu):
                txt = getattr(pu, "effect", pu.__class__.__name__)
                self.flash_messages.append({"text": txt, "timer": now + 2,
                                            "pos": (WIDTH // 2, HEIGHT // 2), "font_size": 50})
                if hasattr(pu, "effect"):
                    eff = pu.effect
                    if eff == "immunity":
                        self.player.immune = True; self.player.immune_timer = now + pu.duration
                    elif eff == "tail_boost":
                        self.player.tail_multiplier = 2; self.player.tail_boost_timer = now + pu.duration
                        self.score += self.score * pu.score_bonus_factor
                    elif eff == "shield":
                        self.player.shield_active = True; self.player.shield_timer = now + pu.duration
                    elif eff == "slow_motion":
                        self.slow_multiplier = 0.5; self.slow_timer = now + pu.duration
                        self.player.slow_motion_active = True
                    elif eff == "score_multiplier":
                        self.player.score_multiplier = pu.multiplier; self.player.score_multiplier_timer = now + pu.duration
                    elif eff == "magnet":
                        self.player.magnet_active = True; self.player.magnet_timer = now + pu.duration
                elif isinstance(pu, ScoreBoostPickup):
                    self.score += 100
                elif isinstance(pu, SpecialPickup):
                    self.player.special_pickup = pu
                self.powerups.remove(pu)

        # Magnet attraction
        if self.player.magnet_active:
            for pu in self.powerups:
                pu.pos += (self.player.pos - pu.pos) * 0.05

        # Continuous score
        self.score += dt * 10 * self.player.score_multiplier

        # Managers
        self.background.update(dt)
        self.level_manager.update()
        if random.random() < 0.01 * self.level_manager.get_level():
            self.obstacles.append(self.spawn_obstacle())
        self.explosion_manager.update(dt)
        self.camera.update(dt)
        self.flash_messages = [f for f in self.flash_messages if now < f["timer"]]

    # ──────────────────────────────────────────────────────
    # Draw loop
    def draw(self, surf):
        self.background.draw(surf)
        font20 = pygame.font.SysFont("Arial", 20)
        font30 = pygame.font.SysFont("Arial", 30)

        # MENU STATE
        if self.state == "menu":
            surf.fill((0, 0, 0))
            title = pygame.font.SysFont("Arial", 60).render("My Game", True, (255, 255, 255))
            surf.blit(title, (WIDTH//2 - title.get_width()//2, 50))
            for b in self.menu_buttons:
                b.draw(surf)
            return

        # SETTINGS STATE
        if self.state == "settings":
            txt = font30.render("Settings", True, (255, 255, 255))
            surf.blit(txt, (WIDTH//2 - txt.get_width()//2, 30))
            for i, key in enumerate(self.settings_keys):
                y = 100 + i * 60
                val = font30.render(f"{key}: {settings_data[key]}", True, (255, 255, 255))
                surf.blit(val, (WIDTH//2 - 150, y))
                minus = pygame.Rect(WIDTH//2+50, y, 30, 30)
                plus  = pygame.Rect(WIDTH//2+90, y, 30, 30)
                pygame.draw.rect(surf, (100, 100, 100), minus)
                pygame.draw.rect(surf, (100, 100, 100), plus)
                surf.blit(font30.render("-", True, (255, 255, 255)), (minus.x+10, minus.y+3))
                surf.blit(font30.render("+", True, (255, 255, 255)), (plus.x+10, plus.y+3))
            self.settings_back_button.draw(surf)
            return

        # SCOREBOARD STATE
        if self.state == "scoreboard":
            surf.fill((0, 0, 0))
            title = font30.render("Score Board", True, (255, 255, 255))
            surf.blit(title, (WIDTH//2 - title.get_width()//2, 50))
            self.leaderboard.draw(surf)
            self.back_button.draw(surf)
            return

        # ABOUT STATE
        if self.state == "about":
            surf.fill((0, 0, 0))
            title = pygame.font.SysFont("Arial", 50).render(self.about_data.get("title", "About"), True, (255, 255, 255))
            surf.blit(title, (WIDTH//4 - title.get_width()//2, 20))
            self.back_button.draw(surf)
            return

        # PLAYING & GAMEOVER STATES – draw world
        self.player.draw(surf)
        for o in self.obstacles:
            o.draw(surf)
        for pu in self.powerups:
            pu.draw(surf)
        self.emitter.draw(surf)
        self.explosion_manager.draw(surf)

        # Special marker
        if self.player.special_pickup:
            surf.blit(font20.render("Special", True, (128, 0, 128)), (10, 80))
        if self.player.special_active:
            pygame.draw.circle(surf, (255, 0, 255),
                               (int(self.player.pos[0]), int(self.player.pos[1])),
                               self.player.radius + 4, 2)

        # Score / Level / Fuel text line
        bar_h = 30
        score_txt = font20.render(f"Score: {int(self.score)}", True, (255, 255, 255))
        level_txt = font20.render(f"Level: {self.level_manager.get_level()}", True, (255, 255, 255))
        fuel_txt  = font20.render(f"Fuel: {int(self.player.fuel)}", True, (255, 255, 255))
        total_w = score_txt.get_width() + level_txt.get_width() + fuel_txt.get_width() + 40
        x = (WIDTH - total_w) // 2
        for txt in (score_txt, level_txt, fuel_txt):
            surf.blit(txt, (x, 5))
            x += txt.get_width() + 20

        # Active pickup icons + timers
        now = time.time()
        def t_left(attr): return getattr(self.player, attr, 0) - now
        mapping = {
            "immunity":          ("immune",             "immune_timer"),
            "tail_boost":        ("tail_boost",         "tail_boost_timer"),
            "shield":            ("shield_active",      "shield_timer"),
            "slow_motion":       ("slow_motion_active", "slow_timer"),
            "score_multiplier":  ("score_multiplier",   "score_multiplier_timer"),
            "magnet":            ("magnet_active",      "magnet_timer"),
        }
        active = []
        for eff, (flag, tattr) in mapping.items():
            if getattr(self.player, flag, False):
                active.append((eff, int(max(0, t_left(tattr)))))

        icon_x, icon_y = 10, bar_h + 10
        for eff, rem in active:
            draw_powerup_icon(surf, (icon_x + 10, icon_y + 10), eff)
            rem_txt = font20.render(f"{rem}", True, (255, 255, 255))
            surf.blit(rem_txt, (icon_x + 30, icon_y))
            icon_y += 35

        # GameOver overlay
        if self.state == "gameover":
            surf.fill((0, 0, 0))
            go = pygame.font.SysFont("Arial", 50).render("Game Over", True, (255, 255, 255))
            sc = pygame.font.SysFont("Arial", 40).render(f"Score: {int(self.score)}", True, (255, 255, 255))
            surf.blit(go, (WIDTH//2 - go.get_width()//2, HEIGHT//2 - 100))
            surf.blit(sc, (WIDTH//2 - sc.get_width()//2, HEIGHT//2))
            self.restart_button.draw(surf)

        # Flash messages
        for f in self.flash_messages:
            if now < f["timer"]:
                fnt = pygame.font.SysFont("Arial", f["font_size"])
                txt = fnt.render(f["text"], True, (255, 255, 0))
                surf.blit(txt, (f["pos"][0] - txt.get_width() // 2,
                                f["pos"][1] - txt.get_height() // 2))

    # ──────────────────────────────────────────────────────
    # Main loop
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(settings_data["FPS"]) / 1000.0
            w, h = self.window.get_size()
            x_off, y_off = (w - WIDTH) // 2, (h - HEIGHT) // 2
            adj_mouse = (
                pygame.mouse.get_pos()[0] - x_off,
                pygame.mouse.get_pos()[1] - y_off
            )

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                else:
                    self.handle_event(ev, adj_mouse)

            if self.state == "playing":
                self.update(dt)

            # centred play‑area rendering
            play_surface = pygame.Surface((WIDTH, HEIGHT))
            play_surface.fill((0, 0, 0))
            self.draw(play_surface)
            self.window.fill((255, 255, 255))
            self.window.blit(play_surface, (x_off, y_off))
            pygame.display.flip()

        pygame.quit()


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    Game().run()
