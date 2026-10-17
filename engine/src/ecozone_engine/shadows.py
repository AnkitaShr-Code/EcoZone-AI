"""Shadow polygons for a reference time, today or with a change set (engine/RULES.md).

Dependency note: load_bundle, shadow geometry and chunk-shading are WP5a work implemented
here because WP5a has not merged yet. See PR description.
"""

from __future__ import annotations

from collections.abc import Sequence

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from .model import AreaModel, BuildingRow, Change, ShadeTime, SunEntry
from .settings import SETTINGS as S
from .sun import shadow_vector


def _building_shadow(footprint: Polygon, dx: float, dy: float) -> Polygon:
    """Sweep a building footprint in the shadow direction (engine/RULES.md §Shadow sources).

    Returns the union of: original footprint, translated footprint, and all edge quads,
    so concave footprints produce correct shadows.
    """
    translated = _translate(footprint, dx, dy)
    parts: list[Polygon] = [footprint, translated]
    coords = list(footprint.exterior.coords)
    for i in range(len(coords) - 1):
        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]
        quad = Polygon([(x1, y1), (x2, y2), (x2 + dx, y2 + dy), (x1 + dx, y1 + dy)])
        if quad.is_valid and quad.area > 0:
            parts.append(quad)
    result = unary_union(parts)
    if isinstance(result, Polygon):
        return result
    return result.convex_hull  # type: ignore[return-value]


def _translate(geom: Polygon, dx: float, dy: float) -> Polygon:
    coords = [(x + dx, y + dy) for x, y in geom.exterior.coords]
    return Polygon(coords)


def _crown_shadow(cx: float, cy: float, sun: SunEntry) -> Polygon:
    """Shadow disc of a tree crown; crown centre at crown_height_m (engine/RULES.md §Shadow sources)."""
    dx, dy = shadow_vector(sun.altitude_deg, sun.azimuth_deg)
    # Shadow from the crown centre at crown_height_m
    sx = cx + dx * S.crown_height_m
    sy = cy + dy * S.crown_height_m
    return Point(sx, sy).buffer(S.crown_radius_m)


def building_shadows_at(buildings: Sequence[BuildingRow], sun: SunEntry) -> list[Polygon]:
    """Shadow polygon for each building at one reference time, sorted by building id."""
    result: list[Polygon] = []
    dx_per_m, dy_per_m = shadow_vector(sun.altitude_deg, sun.azimuth_deg)
    for b in sorted(buildings, key=lambda r: r.building_id):
        if b.height_m <= 0.0:
            continue
        dx = dx_per_m * b.height_m
        dy = dy_per_m * b.height_m
        fp = b.geometry if isinstance(b.geometry, Polygon) else b.geometry.convex_hull
        result.append(_building_shadow(fp, dx, dy))  # type: ignore[arg-type]
    return result


def tree_positions(site_geom: object, n_trees: int) -> list[tuple[float, float]]:
    """Evenly spaced tree positions along a site LineString."""
    from shapely.geometry import LineString

    line = site_geom if isinstance(site_geom, LineString) else None
    if line is None or n_trees <= 0:
        return []
    length = line.length
    step = length / n_trees
    positions: list[tuple[float, float]] = []
    for i in range(n_trees):
        pt = line.interpolate(step * (i + 0.5))
        positions.append((pt.x, pt.y))
    return positions


def shadows(area: AreaModel, time: ShadeTime, changes: Sequence[Change] = ()) -> list[Polygon]:
    """All shadow polygons for a reference time, optionally with a change set applied.

    Returns a flat list of Polygon objects in EPSG:32643.
    Tree-row and building changes add or modify shadow sources; shade changes add always-on covers.
    """
    sun_entry: SunEntry | None = next((s for s in area.sun if s.time == time), None)
    if sun_entry is None:
        return []

    # Baseline building shadows
    cached = dict(area.baseline_building_shadows).get(time)
    polys = list(cached) if cached is not None else building_shadows_at(area.buildings, sun_entry)
    return [*polys, *change_shadows(area, sun_entry, changes)]


def change_shadows(area: AreaModel, sun_entry: SunEntry, changes: Sequence[Change]) -> list[Polygon]:
    """Shadow polygons added by a change set at one sun position (no baseline building shadows)."""
    polys: list[Polygon] = []

    # Build lookups
    site_by_id = {s.site_id: s for s in area.sites}
    parcel_by_id = {p.parcel_id: p for p in area.parcels}

    for change in sorted(changes, key=lambda c: c.site_id):
        if change.kind == "tree_row":
            site = site_by_id.get(change.site_id)
            if site is None:
                continue
            n_trees = max(0, round(change.quantity))
            for cx, cy in tree_positions(site.geometry, n_trees):
                polys.append(_crown_shadow(cx, cy, sun_entry))

        elif change.kind == "shade":
            # Shade structures always cast shade regardless of sun position
            site = site_by_id.get(change.site_id)
            if site is None:
                continue
            geom = site.geometry
            if geom.geom_type == "Polygon":
                polys.append(geom)  # type: ignore[arg-type]

        elif change.kind == "building":
            parcel = parcel_by_id.get(change.site_id)
            if parcel is None:
                continue
            params = dict(change.params)
            floors = params.get("floors", 0.0)
            h = floors * S.metres_per_floor
            if h <= 0.0:
                continue
            fp = parcel.geometry
            if isinstance(fp, Polygon):
                dx_per_m, dy_per_m = shadow_vector(sun_entry.altitude_deg, sun_entry.azimuth_deg)
                polys.append(_building_shadow(fp, dx_per_m * h, dy_per_m * h))

    return polys


def shade_shadow_polys(area: AreaModel, changes: Sequence[Change]) -> list[Polygon]:
    """Shade-structure polygons from the change set (cover at all reference times)."""
    site_by_id = {s.site_id: s for s in area.sites}
    polys: list[Polygon] = []
    for change in sorted(changes, key=lambda c: c.site_id):
        if change.kind == "shade":
            site = site_by_id.get(change.site_id)
            if site is None:
                continue
            geom = site.geometry
            if isinstance(geom, Polygon):
                polys.append(geom)
    return polys
