"""Shadow offset vector from sun altitude and azimuth (engine/RULES.md).

pvlib stays in pipeline/; the engine only needs the offset vector and the shadow
polygon builder. Sun altitude and azimuth come from the area bundle (meta.json).
"""

from __future__ import annotations

import math


def shadow_vector(altitude_deg: float, azimuth_deg: float) -> tuple[float, float]:
    """Displacement of the shadow tip per metre of height (EPSG:32643, x=East, y=North).

    Sun azimuth is clockwise from North (standard meteorological convention).
    Shadow points away from the sun: if sun is at az=215° (SW), shadow points NE.

    Hand-computed example (used in the golden test):
        altitude=45°, azimuth=180° (due South, high noon) →
        shadow_length = 1 / tan(45°) = 1.0 m per m of height
        shadow direction = North (opposite to South) → (dx=0, dy=+1)
        shadow_vector(45, 180) == (0.0, 1.0)  (within float tolerance)
    """
    alt_rad = math.radians(altitude_deg)
    az_rad = math.radians(azimuth_deg)
    length_per_m = 1.0 / math.tan(alt_rad)
    dx = -math.sin(az_rad) * length_per_m
    dy = -math.cos(az_rad) * length_per_m
    return dx, dy


def delta_theta_deg(canyon_axis_deg: float, wind_from_deg: float) -> float:
    """Angle between the street canyon axis and prevailing wind (0–90°).

    The canyon is bidirectional, so az and az+180° are equivalent.
    Used in the VCI W_a term: W_a = max(0, 100·cos(Δθ)).
    """
    diff = abs((wind_from_deg - canyon_axis_deg) % 360.0)
    if diff > 180.0:
        diff = 360.0 - diff
    # Fold into 0–90°: canyon at 0° is the same as 180°
    if diff > 90.0:
        diff = 180.0 - diff
    return diff
