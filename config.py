# config.py
# All configurable constants and settings

# Increased by 25% (from 800×600 to 1000×750).
WIDTH = 1000
HEIGHT = 750
FPS = 60

# Movement & Physics Settings:
ACCELERATION = 7.5       # Force multiplier applied when moving via mouse.
FRICTION = 0.9           # Damping factor applied each frame.
MIN_THRUST = 100         # Minimum effective distance for maximum thrust (not used in keyboard control).

FUEL_CONSUMPTION_RATE = 30
FUEL_RECHARGE_RATE = 3.0
COOLDOWN_DURATION = 10.0

# Emitter Settings:
EMITTER_CONE_ANGLE = 30  # Total cone angle in degrees.
PARTICLE_RATE = 30       # Particles spawned per second when emitting.

# World scaling:
WORLD_SCALE = 10
WORLD_WIDTH = WIDTH * WORLD_SCALE
WORLD_HEIGHT = HEIGHT * WORLD_SCALE

# Settings dictionary for UI editing.
settings_data = {
    "FPS": FPS,
    "FUEL_CONSUMPTION_RATE": FUEL_CONSUMPTION_RATE,
    "FUEL_RECHARGE_RATE": FUEL_RECHARGE_RATE,
    "COOLDOWN_DURATION": COOLDOWN_DURATION,
    "ACCELERATION": ACCELERATION,
    "FRICTION": FRICTION,
    "MIN_THRUST": MIN_THRUST,
    "EMITTER_CONE_ANGLE": EMITTER_CONE_ANGLE,
    "PARTICLE_RATE": PARTICLE_RATE
}
