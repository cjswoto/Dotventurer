# ui.py
import pygame
import os
from config import WIDTH, HEIGHT

class Button:
    def __init__(self, rect, text, font_size):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = pygame.font.SysFont("Arial", font_size)

    def draw(self, surf):
        pygame.draw.rect(surf, (100,100,100), self.rect)
        txt = self.font.render(self.text, True, (255,255,255))
        surf.blit(txt, (self.rect.centerx - txt.get_width()/2,
                        self.rect.centery - txt.get_height()/2))

    def is_hovered(self, pos):
        return self.rect.collidepoint(pos)


class Leaderboard:
    def __init__(self, filename="scores.txt"):
        self.filename = filename
        self.scores = self.load_scores()

    def load_scores(self):
        if os.path.exists(self.filename):
            with open(self.filename, "r") as f:
                lines = f.readlines()
            scores = []
            for line in lines:
                try:
                    scores.append(float(line.strip()))
                except:
                    pass
            return sorted(scores, reverse=True)[:5]
        return []

    def add_score(self, score):
        self.scores.append(score)
        self.scores = sorted(self.scores, reverse=True)[:5]
        with open(self.filename, "w") as f:
            for s in self.scores:
                f.write(f"{s}\n")

    def draw(self, surf):
        font = pygame.font.SysFont("Arial", 30)
        y = 100
        title = font.render("Leaderboard", True, (255,255,255))
        surf.blit(title, (WIDTH/2 - title.get_width()/2, 50))
        for s in self.scores:
            txt = font.render(f"{s:.0f}", True, (255,255,255))
            surf.blit(txt, (WIDTH/2 - txt.get_width()/2, y))
            y += 40
