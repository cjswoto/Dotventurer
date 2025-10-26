"""Interactive QA harness for the procedural SFX system."""
from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

import pygame

from audio import SFX
from config import WIDTH, HEIGHT

PAN_POSITIONS = [i / 10.0 for i in range(11)]
VOICE_STRESS_EVENT = "hit"


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SFX QA harness")
    parser.add_argument("--disable-audio", action="store_true", help="Run without pygame audio output")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> None:
    pygame.init()
    screen = pygame.display.set_mode((800, 200))
    pygame.display.set_caption("SFX QA Harness")
    font = pygame.font.SysFont("Arial", 16)
    clock = pygame.time.Clock()
    sfx = SFX(enable_audio=not args.disable_audio)

    instructions = [
        "1: Explosion (audition)",
        "2: Spam Hit (hold)",
        "3: Start Thrust Loop",
        "4: Stop Thrust Loop",
        "5: Pan Sweep",
        "6: Duck Loops",
        "7: Voice Cap Stress",
        "ESC: Quit",
    ]
    spam_active = False
    last_sweep = 0.0

    while True:
        dt = clock.tick(60) / 1000.0
        sfx.update(dt)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return
                if event.key == pygame.K_1:
                    sfx.play("explosion")
                if event.key == pygame.K_2:
                    spam_active = True
                if event.key == pygame.K_3:
                    sfx.play_loop("player_thrust")
                if event.key == pygame.K_4:
                    sfx.stop_loop("player_thrust")
                if event.key == pygame.K_5:
                    last_sweep = time.time()
                    for frac in PAN_POSITIONS:
                        x = frac * WIDTH
                        sfx.play("hit", pos=(x, HEIGHT / 2), screen_size=(WIDTH, HEIGHT))
                if event.key == pygame.K_6:
                    sfx.duck("loops", gain_db=-6.0, ms=250)
                if event.key == pygame.K_7:
                    for _ in range(10):
                        sfx.play(VOICE_STRESS_EVENT)
            if event.type == pygame.KEYUP and event.key == pygame.K_2:
                spam_active = False

        if spam_active:
            sfx.play("hit")

        screen.fill((12, 12, 24))
        for i, line in enumerate(instructions):
            text = font.render(line, True, (200, 200, 220))
            screen.blit(text, (20, 20 + i * 20))
        if last_sweep:
            info = font.render(f"Last sweep @ {time.strftime('%H:%M:%S', time.localtime(last_sweep))}", True, (180, 180, 200))
            screen.blit(info, (20, 180))
        pygame.display.flip()


def main(argv: Optional[list[str]] = None) -> None:
    run(parse_args(argv))


if __name__ == "__main__":
    main(sys.argv[1:])
