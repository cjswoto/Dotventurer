"""Interactive QA harness for the procedural SFX system."""

from __future__ import annotations

import argparse
import itertools
import math
import sys
from pathlib import Path

import pygame

from config import WIDTH, HEIGHT
from .recipes import RecipeLibrary
from .renderer import Renderer
from .sfx import SFX
from .utils import log_debug


def _draw_text(surface, font, lines, color=(255, 255, 255)) -> None:
    y = 10
    for line in lines:
        render = font.render(line, True, color)
        surface.blit(render, (10, y))
        y += render.get_height() + 4


def run_harness(base_path: Path) -> None:
    pygame.init()
    screen = pygame.display.set_mode((800, 480))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 16)

    sfx = SFX(enable_audio=True, config_path=str(base_path))
    recipes = RecipeLibrary(base_path / "sfx_recipes.json")
    renderer = Renderer(recipes)

    spam_active = False
    pan_active = False
    pan_angle = 0.0
    loop_running = False
    recipe_cycle = itertools.cycle(recipes.ids())
    last_info = ""

    while True:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return
                if event.key == pygame.K_1:
                    spam_active = not spam_active
                    last_info = f"Spam test: {'on' if spam_active else 'off'}"
                    log_debug(f"qa:spam {'on' if spam_active else 'off'}")
                if event.key == pygame.K_2:
                    pan_active = not pan_active
                    last_info = f"Pan sweep: {'on' if pan_active else 'off'}"
                    log_debug(f"qa:pan {'on' if pan_active else 'off'}")
                if event.key == pygame.K_3:
                    if not loop_running:
                        sfx.play_loop("player_thrust")
                        loop_running = True
                    else:
                        sfx.stop_loop("player_thrust")
                        loop_running = False
                    last_info = "Loop toggled"
                    log_debug("qa:loop toggle")
                if event.key == pygame.K_4:
                    sfx.duck("loops", -6.0, 250)
                    sfx.play("explosion")
                    last_info = "Duck trigger"
                    log_debug("qa:duck trigger")
                if event.key == pygame.K_5:
                    for _ in range(20):
                        sfx.play("hit")
                    last_info = "Voice overflow test"
                    log_debug("qa:voice overflow")
                if event.key == pygame.K_TAB:
                    recipe_id = next(recipe_cycle)
                    renderer.render(recipe_id)  # ensure it renders
                    sfx.play("ui_click")
                    last_info = f"Audition recipe={recipe_id}"
                    log_debug(f"qa:recipe {recipe_id}")
                if event.key == pygame.K_SPACE:
                    sfx.play("special_activate")
                    last_info = "Special activate"
                    log_debug("qa:special activate")
        if spam_active:
            sfx.play("hit")
        if pan_active:
            pan_angle += dt
            x = (math.sin(pan_angle) * 0.5 + 0.5) * WIDTH
            sfx.play("explosion", pos=(x, HEIGHT / 2), screen_size=(WIDTH, HEIGHT))
            last_info = f"Pan gains updated"

        sfx.update(dt)

        screen.fill((20, 20, 20))
        lines = [
            "QA Harness Controls:",
            "1 - Toggle hit spam (cooldown test)",
            "2 - Toggle pan sweep", 
            "3 - Toggle thrust loop", 
            "4 - Explosion + duck loops",
            "5 - Voice overflow stress",
            "TAB - Cycle recipes",
            "SPACE - Special activate",
            "ESC - Quit",
            f"Info: {last_info}",
        ]
        _draw_text(screen, font, lines)
        pygame.display.flip()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="QA harness for procedural SFX")
    parser.add_argument("--assets", default="assets", help="Base asset directory")
    args = parser.parse_args(argv)
    base_path = Path(args.assets)
    run_harness(base_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
