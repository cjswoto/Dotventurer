import math
import sys
import types
import unittest


pygame_stub = types.ModuleType("pygame")
pygame_stub.Surface = lambda *args, **kwargs: None
pygame_stub.SRCALPHA = 0
pygame_stub.draw = types.SimpleNamespace(
    circle=lambda *args, **kwargs: None,
    polygon=lambda *args, **kwargs: None,
    arc=lambda *args, **kwargs: None,
    ellipse=lambda *args, **kwargs: None,
    rect=lambda *args, **kwargs: None,
)
pygame_stub.time = types.SimpleNamespace(get_ticks=lambda: 0)
pygame_stub.font = types.SimpleNamespace(SysFont=lambda *args, **kwargs: types.SimpleNamespace(render=lambda *a, **k: types.SimpleNamespace(get_width=lambda: 0, get_height=lambda: 0)))
pygame_stub.mouse = types.SimpleNamespace(get_pos=lambda: (0, 0), get_pressed=lambda: (False, False, False))
sys.modules.setdefault("pygame", pygame_stub)

from entities_player import Player
from entities_obstacles import Obstacle
from config import WIDTH, HEIGHT


class BoundaryTests(unittest.TestCase):
    def test_player_clamped_to_screen(self):
        player = Player()
        player.pos[0] = WIDTH - player.radius - 1
        player.pos[1] = HEIGHT / 2
        player.vel[0] = 200.0
        player.vel[1] = 0.0

        target = player.pos.copy()
        target[0] = WIDTH * 2
        player.update(0.5, target)

        self.assertLessEqual(player.pos[0], WIDTH - player.radius)
        self.assertGreaterEqual(player.pos[0], player.radius)
        self.assertAlmostEqual(player.vel[0], 0.0, delta=1e-5)

    def test_obstacle_bounces_inside_screen(self):
        obstacle = Obstacle(level=1)
        obstacle.radius = 10
        obstacle.speed = 100
        obstacle.pos[0] = WIDTH - obstacle.radius - 1
        obstacle.pos[1] = HEIGHT / 2
        obstacle.direction = 0

        obstacle.update(0.5, None)

        self.assertLessEqual(obstacle.pos[0], WIDTH - obstacle.radius)
        self.assertGreaterEqual(obstacle.pos[0], obstacle.radius)
        self.assertLess(math.cos(obstacle.direction), 0.0)


if __name__ == "__main__":
    unittest.main()
