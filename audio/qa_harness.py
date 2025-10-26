"""Interactive QA harness for procedural audio events."""

from __future__ import annotations

import math
from itertools import cycle
from typing import List

import pygame

from config import WIDTH, HEIGHT

from .catalog import Catalog
from .sfx import SFX

PAN_SCREEN = (WIDTH, HEIGHT)


class QAHarness:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((800, 240))
        pygame.display.set_caption("Audio QA Harness")
        self.font = pygame.font.SysFont("Arial", 18)
        self.clock = pygame.time.Clock()
        self.sfx = SFX()
        catalog = Catalog.load_default()
        self.catalog = list(catalog.events())
        self.event_iter = cycle(self.catalog)
        self.current = next(self.event_iter)
        self.spam_active = False
        self.spam_timer = 0.0
        self.pan_time = 0.0
        self.pan_active = False
        self.loop_running = False
        self.voice_test = False

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = self._handle_key(event.key)
                elif event.type == pygame.KEYUP and event.key == pygame.K_h:
                    self.spam_active = False
            self._update(dt)
            self.sfx.update(dt)
            self._draw()
        pygame.quit()

    def _handle_key(self, key: int) -> bool:
        if key == pygame.K_ESCAPE:
            return False
        if key == pygame.K_SPACE:
            self.current = next(self.event_iter)
        elif key == pygame.K_RETURN:
            self.sfx.play(self.current.name, pos=(WIDTH // 2, HEIGHT // 2), screen_size=PAN_SCREEN)
        elif key == pygame.K_h:
            self.spam_active = True
            self.spam_timer = 0.0
        elif key == pygame.K_p:
            self.pan_active = not self.pan_active
            self.pan_time = 0.0
        elif key == pygame.K_d:
            if not self.loop_running:
                self.sfx.play_loop("player_thrust", pos=(WIDTH // 2, HEIGHT // 2), screen_size=PAN_SCREEN)
                self.loop_running = True
            self.sfx.play("explosion", pos=(WIDTH // 2, HEIGHT // 2), screen_size=PAN_SCREEN)
            self.sfx.duck("loops", -6.0, 250)
        elif key == pygame.K_l:
            if self.loop_running:
                self.sfx.stop_loop("player_thrust")
                self.loop_running = False
        elif key == pygame.K_v:
            self._voice_overflow_test()
        return True

    def _update(self, dt: float) -> None:
        if self.spam_active:
            self.spam_timer += dt
            while self.spam_timer >= 0.05:
                self.spam_timer -= 0.05
                self.sfx.play("hit")
        if self.pan_active:
            self.pan_time += dt
            pan_pos = (math.sin(self.pan_time) * 0.5 + 0.5) * WIDTH
            gains = self._pan_preview(pan_pos)
            print(f"Pan sweep pos={pan_pos:.1f} gains={gains}")
            self.sfx.play("hit", pos=(pan_pos, HEIGHT // 2), screen_size=PAN_SCREEN)

    def _draw(self) -> None:
        self.screen.fill((20, 20, 20))
        lines: List[str] = [
            "SPACE: next event",
            "ENTER: audition current",
            "H: spam hit (cooldown test)",
            "P: toggle pan sweep",
            "D: duck demo (thrust + explosion)",
            "L: stop thrust loop",
            "V: voice overflow test",
            f"Current event: {self.current.name}",
        ]
        for idx, line in enumerate(lines):
            surf = self.font.render(line, True, (220, 220, 220))
            self.screen.blit(surf, (20, 30 + idx * 24))
        pygame.display.flip()

    def _pan_preview(self, x_pos: float) -> tuple[float, float]:
        width, _ = PAN_SCREEN
        norm = max(-1.0, min(1.0, (x_pos / width) * 2.0 - 1.0))
        theta = (norm + 1.0) * (math.pi / 4.0)
        return math.cos(theta), math.sin(theta)

    def _voice_overflow_test(self) -> None:
        for _ in range(10):
            self.sfx.play("explosion")
        for _ in range(6):
            self.sfx.play("ui_click")


def main() -> None:
    QAHarness().run()


if __name__ == "__main__":
    main()
