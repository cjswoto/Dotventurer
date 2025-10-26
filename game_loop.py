# game_loop.py

import pygame
from config import WIDTH, HEIGHT, settings_data, AUDIO_ENABLED
from game import Game
from audio import SFX

def process_events(game, x_offset, y_offset):
    adjusted = (pygame.mouse.get_pos()[0] - x_offset,
                pygame.mouse.get_pos()[1] - y_offset)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False, adjusted
        game.handle_event(event, adjusted)
    return True, adjusted

def update_game(game, dt):
    game.update(dt)

def render_game(game, screen, game_surface, x_offset, y_offset):
    game_surface.fill((0,0,0))
    game.draw(game_surface)
    screen.fill((255,255,255))
    screen.blit(game_surface, (x_offset, y_offset))
    pygame.display.flip()

def run_game():
    pygame.init()
    clock = pygame.time.Clock()
    info = pygame.display.Info()
    screen = pygame.display.set_mode((info.current_w, info.current_h))
    game_surface = pygame.Surface((WIDTH, HEIGHT))
    sfx = SFX(enable_audio=AUDIO_ENABLED)
    game = Game(sfx=sfx)
    running = True

    while running:
        # Re-read FPS each frame
        FPS = settings_data["FPS"]
        dt = clock.tick(FPS) / 1000.0

        w, h = screen.get_size()
        x_off = (w - WIDTH) // 2
        y_off = (h - HEIGHT) // 2

        running, _ = process_events(game, x_off, y_off)
        update_game(game, dt)
        render_game(game, screen, game_surface, x_off, y_off)

    pygame.quit()

if __name__ == "__main__":
    run_game()
