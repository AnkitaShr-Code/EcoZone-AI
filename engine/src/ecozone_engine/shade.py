"""Chunk shading per reference time, PSS per chunk, block and area (PLANNING.md §PSS)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .model import BuildingRow, ChunkRow, SunEntry
from .settings import SETTINGS
from .sun import shadow_offset

# ---------------------------------------------------------------------------
# Building shadow polygon
# ---------------------------------------------------------------------------


def building_shadow_polygon(footprint: Polygon, dx: float, dy: float) -> BaseGeometry:
    """Swept polygon: union of the footprint, its translate, and one quad per exterior edge.

    Using edge quads keeps concave footprints correct (engine/RULES.md §Shadow sources).
    """
    from shapely import affinity

    translated = affinity.translate(footprint, dx, dy)
    parts: list[BaseGeometry] = [footprint, translated]
    coords = list(footprint.exterior.coords)
    for i in range(len(coords) - 1):
        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]
        parts.append(
            Polygon(
                [
                    (x1, y1),
                    (x2, y2),
                    (x2 + dx, y2 + dy),
                    (x1 + dx, y1 + dy),
                ]
            )
        )
    return unary_union(parts)


# ---------------------------------------------------------------------------
# Tree crown shadow
# ---------------------------------------------------------------------------


def tree_crown_shadow(cx: float, cy: float, sun: SunEntry) -> BaseGeometry:
    """Circular shadow for one tree crown at (cx, cy), using prototype settings.

    PLANNING.md §PSS domain rules: "Tree crowns: discs of the settings radius,
    raised to the settings crown height."
    """
    dx, dy = shadow_offset(sun.azimuth_deg, sun.altitude_deg, SETTINGS.tree_crown_height_m)
    # Shadow centre = crown centre projected onto the ground along the sun direction
    shadow_cx = cx + dx
    shadow_cy = cy + dy
    return Point(shadow_cx, shadow_cy).buffer(SETTINGS.tree_crown_radius_m)


# ---------------------------------------------------------------------------
# Shade structure shadow
# ---------------------------------------------------------------------------


def shade_structure_shadow(geom: BaseGeometry, sun: SunEntry) -> BaseGeometry:
    """Shadow of a shade structure modelled as its footprint at 3 m.

    "Shade under a structure counts at every reference time" means the footprint
    itself is always included; we also add the translated polygon.
    """
    from shapely import affinity

    dx, dy = shadow_offset(sun.azimuth_deg, sun.altitude_deg, SETTINGS.shade_structure_height_m)
    translated = affinity.translate(geom, dx, dy)
    return geom.union(translated)


# ---------------------------------------------------------------------------
# Shadow union for one time step
# ---------------------------------------------------------------------------


def shadow_union_at(
    buildings: Sequence[BuildingRow],
    sun: SunEntry,
    extra_polygons: Sequence[BaseGeometry] = (),
) -> BaseGeometry | None:
    """Return the union of all building shadows (plus any extras) at one reference time.

    Returns None when there are no shadow sources (empty area).
    """
    parts: list[BaseGeometry] = []
    for b in buildings:
        if b.height_m <= 0.0:
            continue
        dx, dy = shadow_offset(sun.azimuth_deg, sun.altitude_deg, b.height_m)
        parts.append(building_shadow_polygon(cast(Polygon, b.geometry), dx, dy))
    parts.extend(extra_polygons)
    if not parts:
        return None
    return unary_union(parts)


# ---------------------------------------------------------------------------
# Chunk shading
# ---------------------------------------------------------------------------


def _midpoint(chunk: ChunkRow) -> Point:
    return chunk.geometry.interpolate(0.5, normalized=True)  # type: ignore[return-value]


def compute_chunk_shade(
    chunks: Sequence[ChunkRow],
    buildings: Sequence[BuildingRow],
    sun_entries: Sequence[SunEntry],
) -> dict[str, tuple[bool, bool, bool]]:
    """Return {chunk_id: (shaded_t0, shaded_t1, shaded_t2)} for each chunk.

    A chunk is shaded at time t when its midpoint lies inside the shadow union at t.
    """
    assert len(sun_entries) == SETTINGS.pss_n_times, "expected exactly 3 shade times"
    # Precompute shadow unions per time
    shadow_unions: list[BaseGeometry | None] = [shadow_union_at(buildings, s) for s in sun_entries]
    result: dict[str, tuple[bool, bool, bool]] = {}
    for chunk in chunks:
        mp = _midpoint(chunk)
        flags: list[bool] = []
        for su in shadow_unions:
            flags.append(bool(su is not None and su.contains(mp)))
        result[chunk.chunk_id] = (flags[0], flags[1], flags[2])
    return result


# ---------------------------------------------------------------------------
# PSS from shade flags
# ---------------------------------------------------------------------------


def chunk_pss(shade: tuple[bool, bool, bool]) -> float:
    """PSS_chunk = 100 * (shaded times) / 3  (PLANNING.md §PSS)."""
    return 100.0 * sum(shade) / SETTINGS.pss_n_times


def block_pss(chunks: Sequence[ChunkRow]) -> float:
    """Length-weighted mean of chunk PSS for chunks belonging to this block."""
    total_length = sum(c.length_m for c in chunks)
    if total_length == 0.0:
        return 0.0
    return sum(c.pss * c.length_m for c in chunks) / total_length


def area_pss(chunks: Sequence[ChunkRow]) -> float:
    """Length-weighted mean of all chunk PSS values."""
    return block_pss(chunks)


# ---------------------------------------------------------------------------
# Shadow polygons list (public shadows() entry point helper)
# ---------------------------------------------------------------------------


def building_shadows_at_time(buildings: Sequence[BuildingRow], sun: SunEntry) -> list[Polygon]:
    """Shadow polygon for each building at one reference time."""
    out: list[Polygon] = []
    for b in buildings:
        if b.height_m <= 0.0:
            continue
        dx, dy = shadow_offset(sun.azimuth_deg, sun.altitude_deg, b.height_m)
        shadow = building_shadow_polygon(cast(Polygon, b.geometry), dx, dy)
        # Return as Polygon (may be MultiPolygon for complex footprints; flatten)
        if shadow.geom_type == "Polygon":
            out.append(shadow)  # type: ignore[arg-type]
        elif shadow.geom_type == "MultiPolygon":
            out.extend(list(shadow.geoms))  # type: ignore[arg-type]
        else:
            geoms = getattr(shadow, "geoms", [shadow])
            for g in geoms:
                if g.geom_type == "Polygon":
                    out.append(g)  # type: ignore[arg-type]
    return out
