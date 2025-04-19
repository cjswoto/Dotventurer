# entities.py

# re‑export everything, including the newly added PowerUp

from entities_utils import (
    regular_polygon,
    star_polygon,
    irregular_polygon,
    check_collision
)

from entities_player import Player

from entities_obstacles import (
    Obstacle,
    ChaserObstacle,
    SplitterObstacle
)

from entities_particle import Particle

from entities_emitter import Emitter

from entities_pickups import (
    PowerUp,
    ExtraFuelPickup,
    ScoreBoostPickup,
    BoostPickup,
    SpecialPickup,
    ShieldPickup,
    SlowMotionPickup,
    ScoreMultiplierPickup,
    MagnetPickup
)
