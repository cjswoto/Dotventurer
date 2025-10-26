# game.py
# ──────────────────────────────────────────────────────────────
# Updated build – April 19 2025
# • About‑screen columns already integrated
# • ExtraFuelPickup renamed ⇒ ImmunityPickup
# • Timed‑pickup descriptions/durations aligned (30 s)
# • PowerUp now instantly refuels & clears cooldown
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
    Player, Obstacle, PowerUp, ImmunityPickup,
    ScoreBoostPickup, BoostPickup, SpecialPickup,
    ShieldPickup, SlowMotionPickup, ScoreMultiplierPickup,
    MagnetPickup, check_collision, ChaserObstacle,
    SplitterObstacle, Emitter
)
from entities_utils import regular_polygon, irregular_polygon
from background import Background
from managers import LevelManager, ExplosionManager, Camera, Timer
from ui import Button, Leaderboard
from logging_utils import log_line


def clamp(v, lo, hi):
    return max(lo, min(v, hi))


# ──────────────────────────────────────────────────────────────
# Helper – 20 px pickup icon (no surrounding frame)
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
        pygame.draw.ellipse(surface, col, (x - r, y - r / 2, r * 2, r))
    else:
        pygame.draw.polygon(surface, col, regular_polygon((x, y), r, sides, rot))


# ──────────────────────────────────────────────────────────────
# Main Game class
# ──────────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        log_line("Game.__init__ start")
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
        self.settings_keys  = [
            "FPS",
            "FUEL_CONSUMPTION_RATE",
            "FUEL_RECHARGE_RATE",
            "COOLDOWN_DURATION",
            "SOUND_MUSIC_VOLUME",
            "SOUND_SFX_VOLUME"
        ]
        self.settings_steps = {
            "FPS": 5,
            "FUEL_CONSUMPTION_RATE": 5,
            "FUEL_RECHARGE_RATE": 0.1,
            "COOLDOWN_DURATION": 0.5,
            "SOUND_MUSIC_VOLUME": 0.05,
            "SOUND_SFX_VOLUME": 0.05
        }
        self.settings_bounds = {
            "SOUND_MUSIC_VOLUME": (0.0, 1.0),
            "SOUND_SFX_VOLUME": (0.0, 1.0)
        }
        self.settings_back_button = Button((WIDTH/2-50, HEIGHT-80, 100, 40), "Back", 30)
        self.back_button    = Button((WIDTH/2-50, HEIGHT-80, 100, 40), "Back", 30)
        self.restart_button = Button((WIDTH/2-100,HEIGHT/2+50, 200, 50), "Restart", 30)

        self.about_data = self._load_about()

        self.music_volume = settings_data.get("SOUND_MUSIC_VOLUME", 0.5)
        self.sfx_volume = settings_data.get("SOUND_SFX_VOLUME", 0.7)
        self.audio_available = False
        self.music_channel = None
        self.sfx_channel = None
        self.music_sound = None
        self.sfx_sounds = {}
        self.sample_rate = 44100
        self._init_audio()

    # ──────────────────────────────────────────────────────
    # Utility loaders
    def _load_about(self):
        try:
            with open("about.json", "r") as f:
                return json.load(f)
        except Exception:
            return {"title": "About", "objects": [], "instructions": ["No about data available."]}

    def _init_audio(self):
        log_line("Game._init_audio start")
        try:
            pygame.mixer.init(frequency=self.sample_rate, size=-16, channels=1)
        except pygame.error:
            log_line("Game._init_audio mixer_init_failed")
            self.audio_available = False
            return

        self.audio_available = True
        pygame.mixer.set_num_channels(8)
        self.music_channel = pygame.mixer.Channel(0)
        self.sfx_channel = pygame.mixer.Channel(1)

        try:
            self.music_sound = self._generate_music_track()
            self.sfx_sounds = self._generate_sfx_bank()
        except pygame.error:
            log_line("Game._init_audio sound_generation_failed")
            self.audio_available = False
            return

        self._apply_volume_settings()
        if self.music_channel and self.music_sound:
            self.music_channel.play(self.music_sound, loops=-1)

    def _synthesize_wave(self, frequencies, duration, fade_out=0.0):
        log_line("Game._synthesize_wave")
        samples = int(self.sample_rate * duration)
        if samples <= 0:
            return np.zeros(1, dtype=np.float32)
        t = np.linspace(0, duration, samples, False)
        wave = np.zeros(samples, dtype=np.float32)
        for freq, amplitude in frequencies:
            wave += amplitude * np.sin(2 * math.pi * freq * t)
        max_val = np.max(np.abs(wave))
        if max_val > 0:
            wave /= max_val
        if fade_out > 0:
            fade_samples = min(samples, int(self.sample_rate * fade_out))
            envelope = np.linspace(1, 0, fade_samples, dtype=np.float32)
            wave[-fade_samples:] *= envelope
        return wave

    def _wave_to_sound(self, wave):
        log_line("Game._wave_to_sound")
        normalized = wave
        max_val = np.max(np.abs(normalized))
        if max_val > 0:
            normalized = normalized / max_val
        audio = np.ascontiguousarray((normalized * 32767).astype(np.int16))
        return pygame.sndarray.make_sound(audio)

    def _generate_music_track(self):
        log_line("Game._generate_music_track")
        motif = np.concatenate([
            self._synthesize_wave([(196, 0.7), (392, 0.3)], 1.0, fade_out=0.2),
            self._synthesize_wave([(246, 0.7), (493, 0.3)], 1.0, fade_out=0.2),
            self._synthesize_wave([(220, 0.7), (440, 0.3)], 1.0, fade_out=0.2),
            self._synthesize_wave([(262, 0.7), (523, 0.3)], 1.0, fade_out=0.3)
        ])
        loop = np.tile(motif, 2)
        return self._wave_to_sound(loop)

    def _generate_sfx_bank(self):
        log_line("Game._generate_sfx_bank")
        return {
            "explosion": self._wave_to_sound(
                self._synthesize_wave([(90, 1.0), (45, 0.8), (30, 0.5)], 0.5, fade_out=0.4)
            ),
            "pickup": self._wave_to_sound(
                self._synthesize_wave([(660, 0.8), (880, 0.6), (1320, 0.3)], 0.25, fade_out=0.1)
            ),
            "special": self._wave_to_sound(
                self._synthesize_wave([(520, 0.7), (780, 0.4)], 0.4, fade_out=0.2)
            ),
            "gameover": self._wave_to_sound(
                self._synthesize_wave([(180, 0.8), (120, 0.6)], 0.6, fade_out=0.4)
            )
        }

    def _apply_volume_settings(self):
        log_line("Game._apply_volume_settings")
        self.music_volume = settings_data.get("SOUND_MUSIC_VOLUME", self.music_volume)
        self.sfx_volume = settings_data.get("SOUND_SFX_VOLUME", self.sfx_volume)
        if not self.audio_available:
            return
        if self.music_channel and self.music_sound:
            self.music_channel.set_volume(self.music_volume)
        for sound in self.sfx_sounds.values():
            sound.set_volume(self.sfx_volume)

    def _play_sfx(self, key):
        log_line(f"Game._play_sfx {key}")
        if not self.audio_available:
            return
        sound = self.sfx_sounds.get(key)
        if not sound:
            return
        sound.set_volume(self.sfx_volume)
        channel = pygame.mixer.find_channel()
        if channel:
            channel.play(sound)
        elif self.sfx_channel:
            self.sfx_channel.play(sound)

    def _add_explosion(self, pos):
        log_line("Game._add_explosion")
        self.explosion_manager.add(pos)
        self._play_sfx("explosion")

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
                        lo, hi = self.settings_bounds.get(key, (0, 1e9))
                        settings_data[key] = clamp(settings_data[key] - self.settings_steps[key], lo, hi)
                        if key in self.settings_bounds:
                            self._apply_volume_settings()
                    elif plus.collidepoint(pos):
                        lo, hi = self.settings_bounds.get(key, (0, 1e9))
                        settings_data[key] = clamp(settings_data[key] + self.settings_steps[key], lo, hi)
                        if key in self.settings_bounds:
                            self._apply_volume_settings()
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
            self._add_explosion(o.pos.copy())
        self.obstacles.clear()
        self.score += bonus
        self.player.special_active = True
        self.player.special_timer  = 3
        self.player.special_pickup = None
        self._play_sfx("special")

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

        self.player.fuel = min(self.player.max_fuel, self.player.fuel + FUEL_RECHARGE_RATE * dt)
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
                    self._add_explosion(o.pos.copy())
                    if hasattr(o, "split"): self.obstacles.extend(o.split())
                    self.obstacles.remove(o)
                    continue
                self._add_explosion(self.player.pos.copy())
                self.camera.shake(0.5, 15)
                self.state = "gameover"
                self._play_sfx("gameover")
                return

        # Particles vs obstacle
        for o in self.obstacles[:]:
            for p in self.emitter.particles[:]:
                if check_collision(p, o):
                    self.score += o.score_value
                    self.flash_messages.append({"text": str(o.score_value), "timer": now + 1.5,
                                                "pos": (int(o.pos[0]), int(o.pos[1])), "font_size": 25})
                    if o.explode: self._add_explosion(o.pos.copy())
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
                    if o.explode: self._add_explosion(o.pos.copy())
                    if hasattr(o, "split"): self.obstacles.extend(o.split())
                    self.obstacles.remove(o)
                    break

        # Spawn new pickups
        if self.power_timer.expired():
            new_pick = random.choice([
                PowerUp, ImmunityPickup, ScoreBoostPickup, BoostPickup,
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

                if isinstance(pu, PowerUp):
                    # Instant refuel & cooldown clear
                    self.player.fuel = self.player.max_fuel
                    self.player.emitting_cooldown = False
                    self.player.cooldown_timer = 0

                elif hasattr(pu, "effect"):
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
                self._play_sfx("pickup")

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
            title = pygame.font.SysFont("Arial", 60).render("Dotventure", True, (255, 255, 255))
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
                current = settings_data[key]
                if key in self.settings_bounds:
                    display_val = f"{current:.2f}"
                else:
                    display_val = current
                val = font30.render(f"{key}: {display_val}", True, (255, 255, 255))
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

        # ABOUT STATE (multi‑column panel)
        if self.state == "about":
            surf.fill(tuple(self.about_data.get("panel_background_color", [0, 0, 0])))
            title_font = pygame.font.SysFont("Arial", 50)
            desc_font  = pygame.font.SysFont("Arial", 20)
            instr_font = pygame.font.SysFont("Arial", 20)

            title_surf = title_font.render(self.about_data.get("title", "About"), True, (255,255,255))
            surf.blit(title_surf, (WIDTH//2 - title_surf.get_width()//2, 30))
            self.back_button.draw(surf)

            # 2 columns
            objects = self.about_data.get("objects", [])
            mid = (len(objects)+1)//2
            cols = [objects[:mid], objects[mid:]]
            col_x = [60, WIDTH//2 + 20]
            spacing = 34

            for ci, col in enumerate(cols):
                for i, obj in enumerate(col):
                    y = 100 + i*spacing
                    r = obj.get("size", 12)
                    color = tuple(obj.get("color", [255,255,255]))
                    shape = obj.get("shape", "circle")
                    cx = col_x[ci]
                    cy = y
                    if shape == "circle":
                        pygame.draw.circle(surf, color, (cx+r, cy+r), r)
                    elif shape == "ellipse":
                        pygame.draw.ellipse(surf, color, (cx, cy+r//2, r*2, r))
                    elif shape == "rectangle":
                        pygame.draw.rect(surf, color, (cx, cy, r*2, r*2))
                    elif shape == "diamond":
                        pygame.draw.polygon(surf, color, [(cx+r, cy), (cx+2*r, cy+r), (cx+r, cy+2*r), (cx, cy+r)])
                    elif shape == "triangle":
                        pygame.draw.polygon(surf, color, [(cx+r, cy), (cx+2*r, cy+2*r), (cx, cy+2*r)])
                    elif shape == "pentagon":
                        pygame.draw.polygon(surf, color, regular_polygon((cx+r, cy+r), r, 5))
                    elif shape == "hexagon":
                        pygame.draw.polygon(surf, color, regular_polygon((cx+r, cy+r), r, 6))
                    elif shape == "octagon":
                        pygame.draw.polygon(surf, color, regular_polygon((cx+r, cy+r), r, 8))
                    elif shape == "star":
                        spikes = obj.get("spikes", 5)
                        inner = obj.get("inner_factor", 0.5)
                        pts=[]
                        for s in range(spikes*2):
                            angle = s*math.pi/spikes
                            rad = r if s%2==0 else int(r*inner)
                            pts.append((cx+r+math.cos(angle)*rad, cy+r+math.sin(angle)*rad))
                        pygame.draw.polygon(surf, color, pts)
                    elif shape == "irregular":
                        sides = obj.get("sides", 8)
                        var = obj.get("variation", 0.4)
                        pygame.draw.polygon(surf, color, irregular_polygon((cx+r, cy+r), r, sides, var))

                    label = f"{obj.get('name','')}: {obj.get('description','')}"
                    surf.blit(desc_font.render(label, True, (255,255,255)), (cx + r*2 + 10, cy))

            # Instructions
            y_offset = 100 + max(len(cols[0]), len(cols[1]))*spacing + 20
            for line in self.about_data.get("instructions", []):
                instr = instr_font.render(line, True, (200,200,200))
                surf.blit(instr, (WIDTH//2 - instr.get_width()//2, y_offset))
                y_offset += 24
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
        mapping = {
            "immunity":          ("immune",             "immune_timer"),
            "tail_boost":        ("tail_boost",         "tail_boost_timer"),
            "shield":            ("shield_active",      "shield_timer"),
            "slow_motion":       ("slow_motion_active", "slow_timer"),
            "score_multiplier":  ("score_multiplier",   "score_multiplier_timer"),
            "magnet":            ("magnet_active",      "magnet_timer"),
        }
        active = [(eff, int(max(0, getattr(self.player, tattr, 0) - now)))
                  for eff, (flag, tattr) in mapping.items()
                  if getattr(self.player, flag, False)]

        icon_x, icon_y = 10, bar_h + 10
        for eff, rem in active:
            draw_powerup_icon(surf, (icon_x + 10, icon_y + 10), eff)
            surf.blit(font20.render(f"{rem}", True, (255, 255, 255)), (icon_x + 30, icon_y))
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
            if time.time() < f["timer"]:
                txt = pygame.font.SysFont("Arial", f["font_size"]).render(f["text"], True, (255, 255, 0))
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
            adj_mouse = (pygame.mouse.get_pos()[0] - x_off,
                         pygame.mouse.get_pos()[1] - y_off)

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                else:
                    self.handle_event(ev, adj_mouse)

            if self.state == "playing":
                self.update(dt)

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
