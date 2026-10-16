"""Shadow polygons for a reference time, today or with a change set."""

from __future__ import annotations

from collections.abc import Sequence

from shapely.geometry import Polygon

from ._stub import NotImplementedYetError
from .model import AreaModel, Change, ShadeTime


def shadows(area: AreaModel, time: ShadeTime, changes: Sequence[Change] = ()) -> list[Polygon]:
    raise NotImplementedYetError("shadows", "WP5a")
