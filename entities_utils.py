# entities_utils.py

import math
import random
import numpy as np

def regular_polygon(center, radius, num_sides, rotation=0):
    cx, cy = center
    pts = []
    for i in range(num_sides):
        angle = 2 * math.pi * i / num_sides + rotation
        pts.append((cx + radius * math.cos(angle),
                    cy + radius * math.sin(angle)))
    return pts

def star_polygon(center, outer_radius, inner_radius, spikes, rotation=0):
    cx, cy = center
    pts = []
    for i in range(2 * spikes):
        angle = math.pi * i / spikes + rotation
        r = outer_radius if (i % 2 == 0) else inner_radius
        pts.append((cx + r * math.cos(angle),
                    cy + r * math.sin(angle)))
    return pts

def irregular_polygon(center, radius, num_sides, variation=0.3, rotation=0):
    cx, cy = center
    pts = []
    for i in range(num_sides):
        angle = 2 * math.pi * i / num_sides + rotation
        r = radius * (1 + random.uniform(-variation, variation))
        pts.append((cx + r * math.cos(angle),
                    cy + r * math.sin(angle)))
    return pts

def check_collision(a, b):
    """Return True if objects a and b overlap based on their pos and radius."""
    distance = np.linalg.norm(a.pos - b.pos)
    return distance < (a.radius + b.radius)
