# game.py
import pygame
import numpy as np
import random
import time

from config import WIDTH, HEIGHT, FPS, WORLD_WIDTH, WORLD_HEIGHT, settings_data, FUEL_CONSUMPTION_RATE, \
    FUEL_RECHARGE_RATE, COOLDOWN_DURATION
from entities import (
    Player, Obstacle, PowerUp, ExtraFuelPickup, ScoreBoostPickup, BoostPickup, SpecialPickup,
    Emitter, check_collision, ChaserObstacle, SplitterObstacle
)
from background import Background
from managers import LevelManager, ExplosionManager, Camera, Timer
from ui import Button, Leaderboard

pygame.init()
# Maximize the window (outer window maximized), but our game surface stays fixed.
info = pygame.display.Info()
window_size = (info.current_w, info.current_h)
screen = pygame.display.set_mode(window_size)
clock = pygame.time.Clock()


class Game:
    def __init__(self):
        self.state = "menu"
        self.player = Player()
        self.player.special_pickup = None
        self.player.special_active = False
        self.player.special_timer = 0
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
        self.menu_buttons = [
            Button((WIDTH / 2 - 100, HEIGHT / 2 - 80, 200, 50), "Start Game", 30),
            Button((WIDTH / 2 - 100, HEIGHT / 2 - 20, 200, 50), "Settings", 30),
            Button((WIDTH / 2 - 100, HEIGHT / 2 + 40, 200, 50), "Score Board", 30),
            Button((WIDTH / 2 - 100, HEIGHT / 2 + 100, 200, 50), "About", 30)
        ]
        self.settings_keys = ["FPS", "FUEL_CONSUMPTION_RATE", "FUEL_RECHARGE_RATE", "COOLDOWN_DURATION"]
        self.settings_steps = {"FPS": 5, "FUEL_CONSUMPTION_RATE": 5, "FUEL_RECHARGE_RATE": 0.1,
                               "COOLDOWN_DURATION": 0.5}
        self.settings_back_button = Button((WIDTH / 2 - 50, HEIGHT - 80, 100, 40), "Back", 30)
        self.back_button = Button((WIDTH / 2 - 50, HEIGHT - 80, 100, 40), "Back", 30)
        self.restart_button = Button((WIDTH / 2 - 100, HEIGHT / 2 + 50, 200, 50), "Restart", 30)
        self.camera_pos = self.player.pos.copy()

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
        # Use adjusted_pos if provided, otherwise raw.
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
            elif self.state == "settings":
                font = pygame.font.SysFont("Arial", 30)
                for i, key in enumerate(self.settings_keys):
                    y = 100 + i * 60
                    minus_rect = pygame.Rect(WIDTH / 2 + 50, y, 30, 30)
                    plus_rect = pygame.Rect(WIDTH / 2 + 90, y, 30, 30)
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
            # --- Transform mouse coordinates into world coordinates ---
            mouse_window = np.array(pygame.mouse.get_pos())
            window_size = np.array(pygame.display.get_surface().get_size())
            x_offset = (window_size[0] - WIDTH) // 2
            y_offset = (window_size[1] - HEIGHT) // 2
            adjusted_mouse = mouse_window - np.array([x_offset, y_offset])
            # The game surface is fixed in size; its center corresponds to camera_pos.
            world_mouse = self.camera_pos + (adjusted_mouse - np.array([WIDTH / 2, HEIGHT / 2]))

            # Now update player using the transformed target.
            self.player.update(dt, world_mouse)
            if self.player.special_active:
                self.player.special_timer -= dt
                if self.player.special_timer <= 0:
                    self.player.special_active = False
            margin_x = WIDTH / 8
            margin_y = HEIGHT / 8
            screen_center = np.array([WIDTH / 2, HEIGHT / 2])
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
                self.player.fuel -= FUEL_CONSUMPTION_RATE * dt
                if self.player.fuel < 0:
                    self.player.fuel = 0
                    self.player.emitting_cooldown = True
                    self.player.cooldown_timer = COOLDOWN_DURATION
                emitting = True
            else:
                emitting = False
            effective_recharge = FUEL_RECHARGE_RATE * (1 + 0.1 * boost_count)
            self.player.fuel = min(self.player.max_fuel, self.player.fuel + effective_recharge * dt)
            if self.player.emitting_cooldown:
                self.player.cooldown_timer -= dt
                if self.player.cooldown_timer <= 0:
                    self.player.emitting_cooldown = False
            self.emitter.pos = self.player.pos.copy()
            self.emitter.update(dt, emitting)
            for o in self.obstacles:
                o.update(dt, self.player.pos)
            if self.power_timer.expired():
                pickup_choice = random.choice(["power", "extra_fuel", "score_boost", "boost", "special"])
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
                self.power_timer.reset()
            for pu in self.powerups[:]:
                if check_collision(self.player, pu):
                    if isinstance(pu, PowerUp):
                        self.player.fuel = min(self.player.max_fuel, self.player.fuel + 5)
                        self.score += 50
                    elif hasattr(pu, "restore_amount"):
                        self.player.fuel = min(self.player.max_fuel, self.player.fuel + pu.restore_amount)
                    elif isinstance(pu, ScoreBoostPickup):
                        self.score += 100
                    elif isinstance(pu, BoostPickup):
                        self.player.boosts.append(time.time() + 5)
                    elif isinstance(pu, SpecialPickup):
                        self.player.special_pickup = pu
                    self.powerups.remove(pu)
            for o in self.obstacles[:]:
                for p in self.emitter.particles[:]:
                    if check_collision(p, o):
                        self.score += o.score_value
                        if hasattr(o, "split"):
                            self.obstacles.extend(o.split())
                        if random.random() < 0.1:
                            self.powerups.append(SpecialPickup(o.pos.copy()))
                        self.obstacles.remove(o)
                        if p in self.emitter.particles:
                            self.emitter.particles.remove(p)
                        break
            for o in self.obstacles[:]:
                for point in self.player.trail[::5]:
                    if np.linalg.norm(np.array(point) - o.pos) < o.radius:
                        self.obstacles.remove(o)
                        self.score += 25
                        break
            for o in self.obstacles:
                if check_collision(self.player, o):
                    self.explosion_manager.add(self.player.pos.copy())
                    self.camera.shake(0.5, 15)
                    self.state = "gameover"
                    break
            self.score += dt * 10
            self.background.update(dt)
            self.level_manager.update()
            if random.random() < 0.01 * self.level_manager.get_level():
                self.obstacles.append(self.spawn_obstacle())
            self.explosion_manager.update(dt)
            self.camera.update(dt)

    def draw(self, surf):
        self.background.draw(surf)
        font = pygame.font.SysFont("Arial", 30)
        if self.state == "menu":
            title_font = pygame.font.SysFont("Arial", 60)
            title_text = title_font.render("My Game", True, (255, 255, 255))
            surf.blit(title_text, (WIDTH / 2 - title_text.get_width() / 2, 50))
            for button in self.menu_buttons:
                button.draw(surf)
        elif self.state == "settings":
            title_text = font.render("Settings", True, (255, 255, 255))
            surf.blit(title_text, (WIDTH / 2 - title_text.get_width() / 2, 30))
            for i, key in enumerate(self.settings_keys):
                y = 100 + i * 60
                setting_text = font.render(f"{key}: {settings_data[key]}", True, (255, 255, 255))
                surf.blit(setting_text, (WIDTH / 2 - 150, y))
                minus_rect = pygame.Rect(WIDTH / 2 + 50, y, 30, 30)
                pygame.draw.rect(surf, (100, 100, 100), minus_rect)
                minus_text = font.render("-", True, (255, 255, 255))
                surf.blit(minus_text,
                          (WIDTH / 2 + 50 + (30 - minus_text.get_width()) / 2, y + (30 - minus_text.get_height()) / 2))
                plus_rect = pygame.Rect(WIDTH / 2 + 90, y, 30, 30)
                pygame.draw.rect(surf, (100, 100, 100), plus_rect)
                plus_text = font.render("+", True, (255, 255, 255))
                surf.blit(plus_text,
                          (WIDTH / 2 + 90 + (30 - plus_text.get_width()) / 2, y + (30 - plus_text.get_height()) / 2))
            self.settings_back_button.draw(surf)
        elif self.state == "scoreboard":
            title_text = font.render("Score Board (Not Implemented)", True, (255, 255, 255))
            surf.blit(title_text, (WIDTH / 2 - title_text.get_width() / 2, 50))
            self.back_button.draw(surf)
        elif self.state == "about":
            title_text = font.render("About (Not Implemented)", True, (255, 255, 255))
            surf.blit(title_text, (WIDTH / 2 - title_text.get_width() / 2, 50))
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
                special_icon = pygame.font.SysFont("Arial", 20).render("Special", True, (128, 0, 128))
                surf.blit(special_icon, (10, 80))
            if self.player.special_active:
                pygame.draw.circle(surf, (255, 0, 255), (int(self.player.pos[0]), int(self.player.pos[1])),
                                   self.player.radius + 4, 2)
            level_txt = pygame.font.SysFont("Arial", 20).render(f"Level: {self.level_manager.get_level()}", True,
                                                                (255, 255, 255))
            surf.blit(level_txt, (10, 30))
            score_txt = pygame.font.SysFont("Arial", 20).render(f"Score: {int(self.score)}", True, (255, 255, 255))
            surf.blit(score_txt, (10, 10))
            fuel_txt = pygame.font.SysFont("Arial", 20).render(f"Fuel: {int(self.player.fuel)}", True, (255, 255, 255))
            surf.blit(fuel_txt, (10, 50))
        elif self.state == "gameover":
            title_text = pygame.font.SysFont("Arial", 50).render("Game Over", True, (255, 255, 255))
            surf.blit(title_text, (WIDTH / 2 - title_text.get_width() / 2, HEIGHT / 2 - 100))
            score_text = pygame.font.SysFont("Arial", 40).render(f"Score: {int(self.score)}", True, (255, 255, 255))
            surf.blit(score_text, (WIDTH / 2 - score_text.get_width() / 2, HEIGHT / 2))
            self.restart_button.draw(surf)


def main():
    game = Game()
    # Create a fixed game surface for the play area.
    game_surface = pygame.Surface((WIDTH, HEIGHT))
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        window_width, window_height = screen.get_size()
        # Calculate offsets to center the fixed game surface.
        x_offset = (window_width - WIDTH) // 2
        y_offset = (window_height - HEIGHT) // 2
        # Adjust mouse position relative to the game_surface.
        mouse_pos_window = np.array(pygame.mouse.get_pos())
        adjusted_mouse_pos = (mouse_pos_window[0] - x_offset, mouse_pos_window[1] - y_offset)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                game.handle_event(event, adjusted_mouse_pos)
            if event.type == pygame.KEYDOWN:
                if game.state == "menu" and event.key == pygame.K_SPACE:
                    game.reset()
                    game.state = "playing"
                if game.state == "gameover" and event.key == pygame.K_r:
                    game.leaderboard.add_score(game.score)
                    game.reset()
                    game.state = "playing"
        if game.state == "playing":
            game.update(dt)
        game_surface.fill((0, 0, 0))
        game.draw(game_surface)
        screen.fill((0, 0, 0))
        screen.blit(game_surface, (x_offset, y_offset))
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
