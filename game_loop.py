# game_loop.py
import pygame
import numpy as np
import time
from config import WIDTH, HEIGHT, FPS
from game import Game


def process_events(game, x_offset, y_offset):
    """Handle incoming events and update game state accordingly."""
    adjusted_mouse_pos = (pygame.mouse.get_pos()[0] - x_offset, pygame.mouse.get_pos()[1] - y_offset)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False, adjusted_mouse_pos
        # Let the Game instance handle its own events.
        game.handle_event(event, adjusted_mouse_pos)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and game.state == "playing":
                game.state = "menu"
            if game.state == "menu" and event.key == pygame.K_SPACE:
                game.reset()
                game.state = "playing"
            if game.state == "gameover" and event.key == pygame.K_r:
                game.leaderboard.add_score(game.score)
                game.reset()
                game.state = "playing"
    return True, adjusted_mouse_pos


def update_game(game, dt):
    """Update game state based on the time delta."""
    if game.state == "playing":
        game.update(dt)


def render_game(game, screen, game_surface, x_offset, y_offset):
    """Render the game onto the screen."""
    # Fill the fixed play area with black.
    game_surface.fill((0, 0, 0))
    game.draw(game_surface)
    # Fill the entire window with white and then draw the play area.
    screen.fill((255, 255, 255))
    screen.blit(game_surface, (x_offset, y_offset))
    pygame.display.flip()


def run_game():
    """Entry point for the game loop."""
    pygame.init()
    clock = pygame.time.Clock()
    info = pygame.display.Info()
    window_size = (info.current_w, info.current_h)
    screen = pygame.display.set_mode(window_size)

    # Create a fixed game surface for the play area.
    game_surface = pygame.Surface((WIDTH, HEIGHT))

    # Initialize the game.
    game = Game()
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        window_width, window_height = screen.get_size()
        # Calculate offsets to center the fixed play area.
        x_offset = (window_width - WIDTH) // 2
        y_offset = (window_height - HEIGHT) // 2

        running, _ = process_events(game, x_offset, y_offset)
        update_game(game, dt)
        render_game(game, screen, game_surface, x_offset, y_offset)

    pygame.quit()


if __name__ == "__main__":
    run_game()
