"""Shadow polygons for a reference time, today or with a change set."""

from __future__ import annotations

from collections.abc import Sequence

from shapely.geometry import Polygon

from .model import AreaModel, Change, ShadeTime
from .shade import building_shadows_at_time


def shadows(area: AreaModel, time: ShadeTime, changes: Sequence[Change] = ()) -> list[Polygon]:
    """Return shadow polygons at one reference time.

    Baseline (no changes): building shadows only.
    Changes that add tree rows or shade structures will extend this in WP5b.
    """
    if area.meta is None:
        return []
    sun = next((s for s in area.meta.sun if s.time == time), None)
    if sun is None:
        return []
    return building_shadows_at_time(area.buildings, sun)
