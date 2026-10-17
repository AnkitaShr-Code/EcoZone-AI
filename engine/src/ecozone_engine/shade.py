"""Chunk shading and Pedestrian Shade Score (docs/PLANNING.md §PSS).

A chunk is shaded at time t when its midpoint lies inside the shadow union.
PSS_chunk = 100 * shaded_times / |T| where T = {13:00, 15:00, 16:00}.
Block PSS = length-weighted mean of chunk PSS values.
"""

from __future__ import annotations

from collections.abc import Sequence

from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from .model import AreaModel, Change, ChunkRow, ShadeByTime, ShadeTime
from .shadows import shade_shadow_polys, shadows


def chunk_shaded_at(chunk: ChunkRow, shadow_union: Polygon | MultiPolygon | None) -> bool:
    """True when the chunk midpoint lies inside the shadow union."""
    if shadow_union is None or shadow_union.is_empty:
        return False
    midpoint = chunk.geometry.interpolate(0.5, normalized=True)
    return bool(shadow_union.contains(midpoint))


def chunk_shade_state(
    chunk: ChunkRow,
    shadow_unions: dict[ShadeTime, Polygon | MultiPolygon | None],
    always_on_polys: list[Polygon],
) -> ShadeByTime:
    """Shade state at each reference time for one chunk.

    Shade structures cast shade at every reference time ('always-on').
    Building and crown shadows depend on the sun position.
    """
    always_union: Polygon | MultiPolygon | None = None
    if always_on_polys:
        always_union_raw = unary_union(always_on_polys)
        always_union = always_union_raw if isinstance(always_union_raw, (Polygon, MultiPolygon)) else None

    midpoint = chunk.geometry.interpolate(0.5, normalized=True)
    always_shaded = bool(always_union is not None and always_union.contains(midpoint))

    times: tuple[ShadeTime, ...] = ("13:00", "15:00", "16:00")
    state: list[bool] = []
    for t in times:
        sun_shadow = shadow_unions.get(t)
        if always_shaded:
            state.append(True)
        elif sun_shadow is None or sun_shadow.is_empty:
            state.append(False)
        else:
            state.append(bool(sun_shadow.contains(midpoint)))
    return (state[0], state[1], state[2])


def build_shadow_unions(
    area: AreaModel, changes: Sequence[Change]
) -> dict[ShadeTime, Polygon | MultiPolygon | None]:
    """Build shadow unions (sun-position-dependent) at each reference time."""
    times: tuple[ShadeTime, ...] = ("13:00", "15:00", "16:00")
    result: dict[ShadeTime, Polygon | MultiPolygon | None] = {}
    for t in times:
        polys = shadows(area, t, changes)
        if not polys:
            result[t] = None
        else:
            u = unary_union(polys)
            result[t] = u if isinstance(u, (Polygon, MultiPolygon)) else None
    return result


def compute_chunk_shading(
    area: AreaModel,
    changes: Sequence[Change] = (),
) -> dict[str, ShadeByTime]:
    """Shade state for every chunk with the given change set applied, sorted by chunk id."""
    shadow_unions = build_shadow_unions(area, changes)
    always_on = shade_shadow_polys(area, changes)

    result: dict[str, ShadeByTime] = {}
    for chunk in sorted(area.chunks, key=lambda c: c.chunk_id):
        result[chunk.chunk_id] = chunk_shade_state(chunk, shadow_unions, always_on)
    return result


def pss_from_shading(shading: ShadeByTime) -> float:
    """PSS for one chunk: 100 * shaded_times / 3."""
    return 100.0 * sum(1 for s in shading if s) / 3.0


def block_pss(
    block_id: str,
    chunks: Sequence[ChunkRow],
    chunk_shading: dict[str, ShadeByTime],
) -> float:
    """Length-weighted mean PSS for one block (0–100)."""
    total_length = 0.0
    weighted_pss = 0.0
    for chunk in chunks:
        if chunk.block_id != block_id:
            continue
        shading = chunk_shading.get(chunk.chunk_id, (False, False, False))
        p = pss_from_shading(shading)
        weighted_pss += chunk.length_m * p
        total_length += chunk.length_m
    if total_length == 0.0:
        return 0.0
    return max(0.0, min(100.0, weighted_pss / total_length))


def area_pss(chunks: Sequence[ChunkRow], chunk_shading: dict[str, ShadeByTime]) -> float:
    """Length-weighted mean PSS across all chunks (0–100)."""
    total_length = 0.0
    weighted_pss = 0.0
    for chunk in sorted(chunks, key=lambda c: c.chunk_id):
        shading = chunk_shading.get(chunk.chunk_id, (False, False, False))
        p = pss_from_shading(shading)
        weighted_pss += chunk.length_m * p
        total_length += chunk.length_m
    if total_length == 0.0:
        return 0.0
    return max(0.0, min(100.0, weighted_pss / total_length))
