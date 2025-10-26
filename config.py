import os

# config.py
# All configurable constants and settings

# Window dimensions (increased 25%: 800×600 → 1000×750)
WIDTH = 1920
HEIGHT = 1080

# Frames per second
FPS = 60

# Movement & Physics Settings
ACCELERATION = 600.0       # Force multiplier when moving via mouse
FRICTION = 0.97           # Damping factor applied each frame
MIN_THRUST = 10         # Distance threshold for max thrust

# Fuel and cooldown
FUEL_CONSUMPTION_RATE = 30
FUEL_RECHARGE_RATE = 3.0
COOLDOWN_DURATION = 10.0

# Audio defaults
SOUND_MUSIC_VOLUME = 0.5
SOUND_SFX_VOLUME = 0.7

# Logging configuration
LOG_ENABLED = os.getenv("DOTVENTURER_LOG_ENABLED", "0") == "1"
LOG_FILE_PATH = "logs/debug.txt"

# Emitter Settings
EMITTER_CONE_ANGLE = 30  # Total cone angle in degrees
PARTICLE_RATE = 30       # Particles spawned per second

# World scaling
WORLD_SCALE = 10
WORLD_WIDTH = WIDTH * WORLD_SCALE
WORLD_HEIGHT = HEIGHT * WORLD_SCALE

# Settings dictionary for UI editing
settings_data = {
    "FPS": FPS,
    "FUEL_CONSUMPTION_RATE": FUEL_CONSUMPTION_RATE,
    "FUEL_RECHARGE_RATE": FUEL_RECHARGE_RATE,
    "COOLDOWN_DURATION": COOLDOWN_DURATION,
    "SOUND_MUSIC_VOLUME": SOUND_MUSIC_VOLUME,
    "SOUND_SFX_VOLUME": SOUND_SFX_VOLUME,
    "ACCELERATION": ACCELERATION,
    "FRICTION": FRICTION,
    "MIN_THRUST": MIN_THRUST,
    "EMITTER_CONE_ANGLE": EMITTER_CONE_ANGLE,
    "PARTICLE_RATE": PARTICLE_RATE
}
