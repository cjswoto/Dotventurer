import pygame
import numpy as np
import random
import time
import sys
import json
import math

from config import WIDTH, HEIGHT, FPS, WORLD_WIDTH, WORLD_HEIGHT, settings_data, FUEL_CONSUMPTION_RATE, FUEL_RECHARGE_RATE, COOLDOWN_DURATION
from entities import (
    Player, Obstacle, PowerUp, ExtraFuelPickup, ScoreBoostPickup, BoostPickup, SpecialPickup,
    ShieldPickup, SlowMotionPickup, ScoreMultiplierPickup, MagnetPickup, check_collision,
    ChaserObstacle, SplitterObstacle, Emitter, regular_polygon, star_polygon, irregular_polygon
)
from background import Background
from managers import LevelManager, ExplosionManager, Camera, Timer
from ui import Button, Leaderboard

pygame.init()
info = pygame.display.Info()
window_size = (info.current_w, info.current_h)
screen = pygame.display.set_mode(window_size)
clock = pygame.time.Clock()

class Game:
    def __init__(self):
        # Set the initial state to "menu"
        self.state = "menu"
        self.player = Player()
        self.player.special_pickup = None
        self.player.special_active = False
        self.player.special_timer = 0
        # Create obstacles
        self.obstacles = [self.spawn_obstacle() for _ in range(5)]
        self.emitter = Emitter(self.player.pos)
        self.powerups = []
        self.power_timer = Timer(7)
        self.background = Background()
        self.level_manager = LevelManager()
        self.leaderboard = Leaderboard()
        self.explosion_manager = ExplosionManager()
        self.camera = Camera()
        self.score = 0
        self.slow_multiplier = 1
        # Menu buttons
        self.menu_buttons = [
            Button((WIDTH/2-100, HEIGHT/2-100, 200, 50), "Start Game", 30),
            Button((WIDTH/2-100, HEIGHT/2-40, 200, 50), "Settings", 30),
            Button((WIDTH/2-100, HEIGHT/2+20, 200, 50), "Score Board", 30),
            Button((WIDTH/2-100, HEIGHT/2+80, 200, 50), "About", 30),
            Button((WIDTH/2-100, HEIGHT/2+140, 200, 50), "Exit", 30)
        ]
        self.settings_keys = ["FPS", "FUEL_CONSUMPTION_RATE", "FUEL_RECHARGE_RATE", "COOLDOWN_DURATION"]
        self.settings_steps = {"FPS": 5, "FUEL_CONSUMPTION_RATE": 5, "FUEL_RECHARGE_RATE": 0.1, "COOLDOWN_DURATION": 0.5}
        self.settings_back_button = Button((WIDTH/2-50, HEIGHT-80, 100, 40), "Back", 30)
        self.back_button = Button((WIDTH/2-50, HEIGHT-80, 100, 40), "Back", 30)
        self.restart_button = Button((WIDTH/2-100, HEIGHT/2+50, 200, 50), "Restart", 30)
        self.camera_pos = self.player.pos.copy()
        # Load the About screen content from JSON
        self.about_data = self.load_about_data()
        # NEW: List to hold flash messages
        self.flash_messages = []

    def load_about_data(self):
        try:
            with open("about.json", "r") as f:
                data = json.load(f)
            return data
        except Exception as e:
            print("Error loading about.json:", e)
            # Fallback minimal About data
            return {
                "panel_background_color": [20, 20, 20],
                "title": "About",
                "objects": [],
                "instructions": ["No About data available."]
            }

    def spawn_obstacle(self):
        choice = random.choice(["base", "chaser", "splitter"])
        level = self.level_manager.get_level() if hasattr(self, "level_manager") else 1
        if choice == "chaser":
            return ChaserObstacle(level, self.player.pos)
        elif choice == "splitter":
            return SplitterObstacle(level, self.player.pos)
        else:
            return Obstacle(level, player_pos=self.player.pos)

    def update_globals_from_settings(self):
        global FPS, FUEL_CONSUMPTION_RATE, FUEL_RECHARGE_RATE, COOLDOWN_DURATION
        FPS = settings_data["FPS"]
        FUEL_CONSUMPTION_RATE = settings_data["FUEL_CONSUMPTION_RATE"]
        FUEL_RECHARGE_RATE = settings_data["FUEL_RECHARGE_RATE"]
        COOLDOWN_DURATION = settings_data["COOLDOWN_DURATION"]

    def reset(self):
        self.player = Player()
        self.player.special_pickup = None
        self.player.special_active = False
        self.player.special_timer = 0
        self.obstacles = [self.spawn_obstacle() for _ in range(5)]
        self.emitter = Emitter(self.player.pos)
        self.powerups = []
        self.power_timer = Timer(7)
        self.score = 0
        self.level_manager = LevelManager()
        self.explosion_manager = ExplosionManager()
        self.camera = Camera()
        self.camera_pos = self.player.pos.copy()
        self.slow_multiplier = 1
        self.flash_messages = []

    def activate_special_ability(self):
        bonus = 0
        for o in self.obstacles[:]:
            bonus += o.score_value
            self.explosion_manager.add(o.pos.copy())
            self.obstacles.remove(o)
        self.score += bonus
        self.player.special_active = True
        self.player.special_timer = 3
        self.player.special_pickup = None

    def handle_event(self, event, adjusted_pos=None):
        pos = adjusted_pos if adjusted_pos is not None else pygame.mouse.get_pos()
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.state == "menu":
                for button in self.menu_buttons:
                    if button.is_hovered(pos):
                        if button.text == "Start Game":
                            self.reset()
                            self.state = "playing"
                        elif button.text == "Settings":
                            self.state = "settings"
                        elif button.text == "Score Board":
                            self.state = "scoreboard"
                        elif button.text == "About":
                            self.state = "about"
                        elif button.text == "Exit":
                            pygame.quit()
                            sys.exit()
            elif self.state == "settings":
                for i, key in enumerate(self.settings_keys):
                    y = 100 + i * 60
                    minus_rect = pygame.Rect(WIDTH/2+50, y, 30, 30)
                    plus_rect = pygame.Rect(WIDTH/2+90, y, 30, 30)
                    if minus_rect.collidepoint(pos):
                        settings_data[key] -= self.settings_steps[key]
                        if settings_data[key] < 0:
                            settings_data[key] = 0
                        self.update_globals_from_settings()
                    elif plus_rect.collidepoint(pos):
                        settings_data[key] += self.settings_steps[key]
                        self.update_globals_from_settings()
                if self.settings_back_button.is_hovered(pos):
                    self.state = "menu"
            elif self.state in ["scoreboard", "about"]:
                if self.back_button.is_hovered(pos):
                    self.state = "menu"
            elif self.state == "gameover":
                if self.restart_button.is_hovered(pos):
                    self.leaderboard.add_score(self.score)
                    self.reset()
                    self.state = "playing"
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.state == "playing" and self.player.special_pickup is not None:
                self.activate_special_ability()

    def update(self, dt):
        if self.state == "playing":
            now = time.time()
            if self.player.immune and now > self.player.immune_timer:
                self.player.immune = False
            if hasattr(self.player, "tail_boost_timer") and now > self.player.tail_boost_timer:
                self.player.tail_multiplier = 1
            if hasattr(self.player, "score_multiplier_timer") and now > self.player.score_multiplier_timer:
                self.player.score_multiplier = 1
            if self.player.shield_active and now > self.player.shield_timer:
                self.player.shield_active = False
            if hasattr(self, "slow_timer") and now > self.slow_timer:
                self.slow_multiplier = 1
            if self.player.magnet_active and now > self.player.magnet_timer:
                self.player.magnet_active = False

            mouse_window = np.array(pygame.mouse.get_pos())
            window_size = np.array(pygame.display.get_surface().get_size())
            x_offset = (window_size[0]-WIDTH)//2
            y_offset = (window_size[1]-HEIGHT)//2
            adjusted_mouse = mouse_window - np.array([x_offset, y_offset])
            adjusted_mouse[0] = max(0, min(adjusted_mouse[0], WIDTH))
            adjusted_mouse[1] = max(0, min(adjusted_mouse[1], HEIGHT))
            world_mouse = self.camera_pos + (adjusted_mouse - np.array([WIDTH/2, HEIGHT/2]))

            self.player.update(dt, world_mouse)
            if self.player.special_active:
                self.player.special_timer -= dt
                if self.player.special_timer <= 0:
                    self.player.special_active = False

            margin_x = WIDTH/8
            margin_y = HEIGHT/8
            screen_center = np.array([WIDTH/2, HEIGHT/2])
            player_screen_pos = self.player.pos - (self.camera_pos - screen_center)
            if player_screen_pos[0] < margin_x:
                self.camera_pos[0] = self.player.pos[0] - margin_x + screen_center[0]
            elif player_screen_pos[0] > WIDTH - margin_x:
                self.camera_pos[0] = self.player.pos[0] - (WIDTH - margin_x) + screen_center[0]
            if player_screen_pos[1] < margin_y:
                self.camera_pos[1] = self.player.pos[1] - margin_y + screen_center[1]
            elif player_screen_pos[1] > HEIGHT - margin_y:
                self.camera_pos[1] = self.player.pos[1] - (HEIGHT - margin_y) + screen_center[1]

            left_pressed = pygame.mouse.get_pressed()[0]
            current_time = time.time()
            self.player.boosts = [b for b in self.player.boosts if b > current_time]
            boost_count = len(self.player.boosts)
            if left_pressed and not self.player.emitting_cooldown and self.player.fuel > 0:
                self.player.fuel -= FUEL_CONSUMPTION_RATE*dt
                if self.player.fuel < 0:
                    self.player.fuel = 0
                    self.player.emitting_cooldown = True
                    self.player.cooldown_timer = COOLDOWN_DURATION
                emitting = True
            else:
                emitting = False
            effective_recharge = FUEL_RECHARGE_RATE*(1+0.1*boost_count)
            self.player.fuel = min(self.player.max_fuel, self.player.fuel+effective_recharge*dt)
            if self.player.emitting_cooldown:
                self.player.cooldown_timer -= dt
                if self.player.cooldown_timer <= 0:
                    self.player.emitting_cooldown = False

            self.emitter.pos = self.player.pos.copy()
            self.emitter.update(dt, emitting)

            # Opponent update
            for o in self.obstacles:
                o.update(dt*self.slow_multiplier, self.player.pos)
                if o.emit and o.emitter:
                    for p in o.emitter.particles:
                        if check_collision(p, self.player):
                            self.explosion_manager.add(self.player.pos.copy())
                            self.camera.shake(0.5,15)
                            self.state = "gameover"
                            break

            # Pickup generation
            if self.power_timer.expired():
                pickup_choice = random.choice(["power", "extra_fuel", "score_boost", "boost", "special",
                                                 "shield", "slow_motion", "score_multiplier", "magnet"])
                if pickup_choice == "power":
                    self.powerups.append(PowerUp())
                elif pickup_choice == "extra_fuel":
                    self.powerups.append(ExtraFuelPickup())
                elif pickup_choice == "score_boost":
                    self.powerups.append(ScoreBoostPickup())
                elif pickup_choice == "boost":
                    self.powerups.append(BoostPickup())
                elif pickup_choice == "special":
                    self.powerups.append(SpecialPickup(self.player.pos.copy()))
                elif pickup_choice == "shield":
                    self.powerups.append(ShieldPickup())
                elif pickup_choice == "slow_motion":
                    self.powerups.append(SlowMotionPickup())
                elif pickup_choice == "score_multiplier":
                    self.powerups.append(ScoreMultiplierPickup())
                elif pickup_choice == "magnet":
                    self.powerups.append(MagnetPickup())
                self.power_timer.reset()

            # Pickup collision: when a pickup is collected, flash its name.
            for pu in self.powerups[:]:
                if check_collision(self.player, pu):
                    self.flash_messages.append({
                        "text": getattr(pu, "effect_name", pu.__class__.__name__),
                        "timer": time.time() + 2,   # Visible for 2 seconds
                        "pos": (WIDTH//2, HEIGHT//2),
                        "font_size": 50
                    })
                    if hasattr(pu, "effect"):
                        effect = pu.effect
                        if effect == "immunity":
                            self.player.immune = True
                            self.player.immune_timer = time.time() + pu.duration
                        elif effect == "tail_boost":
                            self.player.tail_multiplier = 2
                            self.player.tail_boost_timer = time.time() + pu.duration
                            bonus = self.score * pu.score_bonus_factor
                            self.score += bonus
                        elif effect == "shield":
                            self.player.shield_active = True
                            self.player.shield_timer = time.time() + pu.duration
                        elif effect == "slow_motion":
                            self.slow_multiplier = 0.5
                            self.slow_timer = time.time() + pu.duration
                        elif effect == "score_multiplier":
                            self.player.score_multiplier = pu.multiplier
                            self.player.score_multiplier_timer = time.time() + pu.duration
                        elif effect == "magnet":
                            self.player.magnet_active = True
                            self.player.magnet_timer = time.time() + pu.duration
                    elif isinstance(pu, ScoreBoostPickup):
                        self.score += 100
                    elif isinstance(pu, SpecialPickup):
                        self.player.special_pickup = pu
                    self.powerups.remove(pu)

            if self.player.magnet_active:
                for pu in self.powerups:
                    direction = self.player.pos - pu.pos
                    pu.pos += direction * 0.05

            # When a player's emitter particle hits an opponent, flash its score at that location.
            for o in self.obstacles[:]:
                for p in self.emitter.particles[:]:
                    if check_collision(p, o):
                        self.flash_messages.append({
                            "text": str(o.score_value),
                            "timer": time.time() + 1.5,
                            "pos": (int(o.pos[0]), int(o.pos[1])),
                            "font_size": 25
                        })
                        self.score += o.score_value
                        if o.explode:
                            self.explosion_manager.add(o.pos.copy())
                        if hasattr(o, "split"):
                            self.obstacles.extend(o.split())
                        self.obstacles.remove(o)
                        if p in self.emitter.particles:
                            self.emitter.particles.remove(p)
                        break

            for o in self.obstacles[:]:
                for point in self.player.trail[::5]:
                    if np.linalg.norm(np.array(point)-o.pos) < o.radius:
                        self.score += 25
                        if o.explode:
                            self.explosion_manager.add(o.pos.copy())
                        if hasattr(o, "split"):
                            self.obstacles.extend(o.split())
                        self.obstacles.remove(o)
                        break

            for o in self.obstacles:
                if check_collision(self.player, o):
                    self.explosion_manager.add(self.player.pos.copy())
                    self.camera.shake(0.5,15)
                    self.state = "gameover"
                    break

            self.score += dt * 10 * self.player.score_multiplier
            self.background.update(dt)
            self.level_manager.update()
            if random.random() < 0.01*self.level_manager.get_level():
                self.obstacles.append(self.spawn_obstacle())
            self.explosion_manager.update(dt)
            self.camera.update(dt)

        # Update flash messages: remove expired ones
        current_time = time.time()
        for flash in self.flash_messages[:]:
            if current_time >= flash["timer"]:
                self.flash_messages.remove(flash)

    def draw(self, surf):
        self.background.draw(surf)
        font = pygame.font.SysFont("Arial",30)
        if self.state == "menu":
            surf.fill((0,0,0))
            title_font = pygame.font.SysFont("Arial",60)
            title_text = title_font.render("My Game", True, (255,255,255))
            surf.blit(title_text, (WIDTH/2-title_text.get_width()/2, 50))
            for button in self.menu_buttons:
                button.draw(surf)
        elif self.state == "settings":
            title_text = font.render("Settings", True, (255,255,255))
            surf.blit(title_text, (WIDTH/2-title_text.get_width()/2, 30))
            for i, key in enumerate(self.settings_keys):
                y = 100+i*60
                setting_text = font.render(f"{key}: {settings_data[key]}", True, (255,255,255))
                surf.blit(setting_text, (WIDTH/2-150, y))
                minus_rect = pygame.Rect(WIDTH/2+50, y, 30, 30)
                pygame.draw.rect(surf, (100,100,100), minus_rect)
                minus_text = font.render("-", True, (255,255,255))
                surf.blit(minus_text, (WIDTH/2+50+(30-minus_text.get_width())/2, y+(30-minus_text.get_height())/2))
                plus_rect = pygame.Rect(WIDTH/2+90, y, 30, 30)
                pygame.draw.rect(surf, (100,100,100), plus_rect)
                plus_text = font.render("+", True, (255,255,255))
                surf.blit(plus_text, (WIDTH/2+90+(30-plus_text.get_width())/2, y+(30-plus_text.get_height())/2))
            self.settings_back_button.draw(surf)
        elif self.state == "scoreboard":
            title_text = font.render("Score Board (Not Implemented)", True, (255,255,255))
            surf.blit(title_text, (WIDTH/2-title_text.get_width()/2, 50))
            self.back_button.draw(surf)
        elif self.state == "about":
            # Draw the About title (no background box now)
            title_str = self.about_data.get("title", "About")
            title_text = pygame.font.SysFont("Arial",50).render(title_str, True, (255,255,255))
            surf.blit(title_text, ((WIDTH//4)-(title_text.get_width()//2), 20))
            panel_x = 50
            panel_y = 100
            obj_font = pygame.font.SysFont("Arial",20)  # Smaller text size
            item_height = 35
            wrap_threshold = HEIGHT - 80
            max_right_x = 0

            def wrap_text_lines(text, font, max_width):
                words = text.split()
                lines = []
                current_line = words[0]
                for w in words[1:]:
                    test_line = current_line + " " + w
                    if font.size(test_line)[0] <= max_width:
                        current_line = test_line
                    else:
                        lines.append(current_line)
                        current_line = w
                lines.append(current_line)
                return lines

            column_text_width = (WIDTH // 2) - 120

            for obj in self.about_data.get("objects", []):
                shape = obj.get("shape", "circle")
                color = tuple(obj.get("color", [255,255,255]))
                size = obj.get("size", 12)
                name = obj.get("name", "Object")
                desc = obj.get("description", "")
                if shape == "octagon":
                    pts = regular_polygon((panel_x, panel_y), size, 8)
                    pygame.draw.polygon(surf, color, pts)
                    shape_right = panel_x + size
                elif shape == "irregular":
                    sides = obj.get("sides", 8)
                    variation = obj.get("variation", 0.4)
                    pts = irregular_polygon((panel_x, panel_y), size, sides, variation)
                    pygame.draw.polygon(surf, color, pts)
                    shape_right = panel_x + size
                elif shape == "star":
                    spikes = obj.get("spikes", 5)
                    inner_factor = obj.get("inner_factor", 0.5)
                    pts = star_polygon((panel_x, panel_y), size, size*inner_factor, spikes)
                    pygame.draw.polygon(surf, color, pts)
                    shape_right = panel_x + size
                elif shape == "diamond":
                    pts = regular_polygon((panel_x, panel_y), size, 4, rotation=math.pi/4)
                    pygame.draw.polygon(surf, color, pts)
                    shape_right = panel_x + size
                elif shape == "triangle":
                    pts = regular_polygon((panel_x, panel_y), size, 3)
                    pygame.draw.polygon(surf, color, pts)
                    shape_right = panel_x + size
                elif shape == "rectangle":
                    rect = (panel_x-size, panel_y-size/2, 2*size, size)
                    pygame.draw.rect(surf, color, rect)
                    shape_right = panel_x + size
                elif shape == "ellipse":
                    rect = (panel_x-size, panel_y-size/2, 2*size, size)
                    pygame.draw.ellipse(surf, color, rect)
                    shape_right = panel_x + size
                elif shape == "pentagon":
                    pts = regular_polygon((panel_x, panel_y), size, 5)
                    pygame.draw.polygon(surf, color, pts)
                    shape_right = panel_x + size
                elif shape == "hexagon":
                    pts = regular_polygon((panel_x, panel_y), size, 6)
                    pygame.draw.polygon(surf, color, pts)
                    shape_right = panel_x + size
                else:
                    pygame.draw.circle(surf, color, (panel_x, panel_y), size)
                    shape_right = panel_x + size

                combined_str = f"{name}: {desc}"
                text_lines = wrap_text_lines(combined_str, obj_font, column_text_width)
                text_line_x = panel_x + 40
                text_line_y = panel_y - 15
                line_height = obj_font.get_height() + 2

                text_line_right = 0
                for idx, line in enumerate(text_lines):
                    text_surf = obj_font.render(line, True, (200,200,200))
                    surf.blit(text_surf, (text_line_x, text_line_y + line_height*idx))
                    if text_line_x + text_surf.get_width() > text_line_right:
                        text_line_right = text_line_x + text_surf.get_width()

                bottom_of_text = text_line_y + line_height * len(text_lines)
                current_item_right = max(shape_right, text_line_right)
                if current_item_right > max_right_x:
                    max_right_x = current_item_right
                panel_y = max(panel_y + item_height, bottom_of_text + 15)
                if panel_y + item_height > wrap_threshold:
                    panel_x = max_right_x + 20
                    panel_y = 100
                    max_right_x = panel_x

            instr_font = pygame.font.SysFont("Arial",20)
            inst_y = panel_y + 20
            for line in self.about_data.get("instructions", []):
                rendered_line = instr_font.render(line, True, (200,200,200))
                surf.blit(rendered_line, (panel_x-10, inst_y))
                inst_y += rendered_line.get_height()+3
            self.back_button.draw(surf)
        elif self.state == "playing":
            self.player.draw(surf)
            for o in self.obstacles:
                o.draw(surf)
            for pu in self.powerups:
                pu.draw(surf)
            self.emitter.draw(surf)
            self.explosion_manager.draw(surf)
            if self.player.special_pickup is not None:
                special_icon = pygame.font.SysFont("Arial",20).render("Special", True, (128,0,128))
                surf.blit(special_icon, (10,80))
            if self.player.special_active:
                pygame.draw.circle(surf, (255,0,255), (int(self.player.pos[0]), int(self.player.pos[1])), self.player.radius+4,2)
            level_txt = pygame.font.SysFont("Arial",20).render(f"Level: {self.level_manager.get_level()}", True, (255,255,255))
            surf.blit(level_txt, (10,30))
            score_txt = pygame.font.SysFont("Arial",20).render(f"Score: {int(self.score)}", True, (255,255,255))
            surf.blit(score_txt, (10,10))
            fuel_txt = pygame.font.SysFont("Arial",20).render(f"Fuel: {int(self.player.fuel)}", True, (255,255,255))
            surf.blit(fuel_txt, (10,50))
        elif self.state == "gameover":
            title_text = pygame.font.SysFont("Arial",50).render("Game Over", True, (255,255,255))
            surf.blit(title_text, (WIDTH/2-title_text.get_width()/2, HEIGHT/2-100))
            score_text = pygame.font.SysFont("Arial",40).render(f"Score: {int(self.score)}", True, (255,255,255))
            surf.blit(score_text, (WIDTH/2-score_text.get_width()/2, HEIGHT/2))
            self.restart_button.draw(surf)

        # Draw flash messages (for pickups and opponent destruction)
        current_time = time.time()
        for flash in self.flash_messages[:]:
            if current_time < flash["timer"]:
                flash_font = pygame.font.SysFont("Arial", flash["font_size"])
                text_surf = flash_font.render(flash["text"], True, (255,255,0))
                pos_x = flash["pos"][0] - text_surf.get_width()//2
                pos_y = flash["pos"][1] - text_surf.get_height()//2
                surf.blit(text_surf, (pos_x, pos_y))
            else:
                self.flash_messages.remove(flash)

def main():
    game = Game()
    game_surface = pygame.Surface((WIDTH, HEIGHT))
    running = True
    while running:
        dt = clock.tick(FPS)/1000.0
        window_width, window_height = screen.get_size()
        x_offset = (window_width - WIDTH)//2
        y_offset = (window_height - HEIGHT)//2
        mouse_pos_window = np.array(pygame.mouse.get_pos())
        adjusted_mouse_pos = (mouse_pos_window[0]-x_offset, mouse_pos_window[1]-y_offset)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                game.handle_event(event, adjusted_mouse_pos)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE and game.state=="playing":
                    game.state = "menu"
                if game.state=="menu" and event.key == pygame.K_SPACE:
                    game.reset()
                    game.state = "playing"
                if game.state=="gameover" and event.key == pygame.K_r:
                    game.leaderboard.add_score(game.score)
                    game.reset()
                    game.state = "playing"
        if game.state=="playing":
            game.update(dt)
        game_surface.fill((0,0,0))
        game.draw(game_surface)
        screen.fill((255,255,255))
        screen.blit(game_surface, (x_offset, y_offset))
        pygame.display.flip()
    pygame.quit()

if __name__ == "__main__":
    main()
