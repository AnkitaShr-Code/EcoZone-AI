"""Shadow offset vector from a sun table entry (pvlib stays in pipeline)."""

from __future__ import annotations

import math


def shadow_offset(azimuth_deg: float, altitude_deg: float, height_m: float) -> tuple[float, float]:
    """Return (dx, dy) in EPSG:32643 metres: shadow falls AWAY from the sun.

    Azimuth is clockwise from north; altitude is above the horizon.
    dx is easting, dy is northing.

    Derivation: sun is at bearing az_deg. Shadow is cast in the opposite direction
    (az_deg + 180°).  Length = height_m / tan(altitude_deg).
      dx = sin(az+180) * L = -sin(az) * L
      dy = cos(az+180) * L = -cos(az) * L
    """
    az_rad = math.radians(azimuth_deg)
    alt_rad = math.radians(altitude_deg)
    length = height_m / math.tan(alt_rad)
    return -math.sin(az_rad) * length, -math.cos(az_rad) * length
