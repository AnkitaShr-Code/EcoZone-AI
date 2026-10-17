"""Attribute deltas for the five Repair intervention types (docs/PLANNING.md §Intervention library).

Each apply_* function returns a dict of {block_id: {attr: delta}} describing what changes.
No I/O, no side effects. Shadow geometry is handled in shadows.py; these functions handle
the non-shadow attribute terms only (I_s, G_c, G_buf, d_green, roof_albedo).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .model import AreaModel, BlockRow, Change
from .settings import SETTINGS as S
from .shadows import tree_positions


def _blocks_within(blocks: Sequence[BlockRow], geom_centroid: object, radius_m: float) -> list[BlockRow]:
    """All blocks whose centroid is within radius_m of geom_centroid, sorted by block_id."""
    result: list[BlockRow] = []
    for b in sorted(blocks, key=lambda r: r.block_id):
        if b.geometry.centroid.distance(geom_centroid) <= radius_m:  # type: ignore[arg-type]
            result.append(b)
    return result


BlockDeltas = dict[str, dict[str, float]]
"""block_id → {attribute_name: delta_value}"""


def apply_tree_row(area: AreaModel, change: Change) -> BlockDeltas:
    """Tree-row attribute deltas: crown area adds to G_c (block) and G_buf (nearby blocks)."""
    site = next((s for s in area.sites if s.site_id == change.site_id), None)
    if site is None:
        return {}
    n_trees = max(0, round(change.quantity))
    crown_area = math.pi * S.crown_radius_m ** 2
    total_crown_area = crown_area * n_trees
    deltas: BlockDeltas = {}

    # Find block that owns this site
    block_id = site.block_id
    if block_id is not None:
        blk = next((b for b in area.blocks if b.block_id == block_id), None)
        if blk is not None and blk.area_m2 > 0.0:
            gc_delta = min(
                100.0 - blk.G_c,
                total_crown_area / blk.area_m2 * 100.0,
            )
            deltas.setdefault(block_id, {})["G_c"] = gc_delta

    # G_buf increment for blocks within 300 m of site centroid
    buffer_area = math.pi * S.green_buffer_radius_m ** 2
    site_centroid = site.geometry.centroid
    for b in _blocks_within(list(area.blocks), site_centroid, S.green_buffer_radius_m):
        gbuf_delta = min(
            100.0 - b.G_buf,
            total_crown_area / buffer_area * 100.0,
        )
        deltas.setdefault(b.block_id, {})
        deltas[b.block_id]["G_buf"] = deltas[b.block_id].get("G_buf", 0.0) + gbuf_delta

    # Reduce d_green: if trees bring green closer to any block
    positions = tree_positions(site.geometry, n_trees)
    for b in sorted(area.blocks, key=lambda r: r.block_id):
        b_centroid = b.geometry.centroid
        if positions:
            nearest = min(b_centroid.distance(  # type: ignore[arg-type]
                type(b_centroid)(cx, cy)) for cx, cy in positions)  # type: ignore[call-arg]
            if nearest < b.d_green:
                d_delta = -(b.d_green - nearest)
                deltas.setdefault(b.block_id, {})
                deltas[b.block_id]["d_green"] = deltas[b.block_id].get("d_green", 0.0) + d_delta

    return deltas


def apply_shade(area: AreaModel, change: Change) -> BlockDeltas:
    """Shade structures affect only shadow geometry (handled in shadows.py); no attribute deltas."""
    return {}


def apply_depave(area: AreaModel, change: Change) -> BlockDeltas:
    """Depave deltas: reduce I_s, increase G_c; update G_buf and d_green for nearby blocks."""
    site = next((s for s in area.sites if s.site_id == change.site_id), None)
    if site is None:
        return {}
    depaved_m2 = change.quantity
    deltas: BlockDeltas = {}

    block_id = site.block_id
    if block_id is not None:
        blk = next((b for b in area.blocks if b.block_id == block_id), None)
        if blk is not None and blk.area_m2 > 0.0:
            is_delta = -min(blk.I_s, depaved_m2 / blk.area_m2 * 100.0)
            gc_delta = min(100.0 - blk.G_c, depaved_m2 * S.depave_green_frac / blk.area_m2 * 100.0)
            deltas[block_id] = {"I_s": is_delta, "G_c": gc_delta}

    green_area = depaved_m2 * S.depave_green_frac
    buffer_area = math.pi * S.green_buffer_radius_m ** 2
    site_centroid = site.geometry.centroid
    for b in _blocks_within(list(area.blocks), site_centroid, S.green_buffer_radius_m):
        gbuf_delta = min(100.0 - b.G_buf, green_area / buffer_area * 100.0)
        deltas.setdefault(b.block_id, {})
        deltas[b.block_id]["G_buf"] = deltas[b.block_id].get("G_buf", 0.0) + gbuf_delta
        site_dist = b.geometry.centroid.distance(site_centroid)  # type: ignore[arg-type]
        if site_dist < b.d_green:
            d_delta = -(b.d_green - site_dist)
            deltas[b.block_id]["d_green"] = deltas[b.block_id].get("d_green", 0.0) + d_delta

    return deltas


def apply_pocket_green(area: AreaModel, change: Change) -> BlockDeltas:
    """Pocket-green deltas: increase G_buf, reduce d_green for blocks within 300 m."""
    site = next((s for s in area.sites if s.site_id == change.site_id), None)
    if site is None:
        return {}
    green_area = change.quantity  # m²
    buffer_area = math.pi * S.green_buffer_radius_m ** 2
    site_centroid = site.geometry.centroid
    deltas: BlockDeltas = {}

    for b in _blocks_within(list(area.blocks), site_centroid, S.green_buffer_radius_m):
        gbuf_delta = min(100.0 - b.G_buf, green_area / buffer_area * 100.0)
        site_dist = b.geometry.centroid.distance(site_centroid)  # type: ignore[arg-type]
        d_delta = -(b.d_green - site_dist) if site_dist < b.d_green else 0.0
        deltas.setdefault(b.block_id, {})
        deltas[b.block_id]["G_buf"] = deltas[b.block_id].get("G_buf", 0.0) + gbuf_delta
        if d_delta < 0.0:
            deltas[b.block_id]["d_green"] = deltas[b.block_id].get("d_green", 0.0) + d_delta

    # Also increase G_c for the block this site is in (if block known)
    block_id = site.block_id
    if block_id is not None:
        blk = next((b for b in area.blocks if b.block_id == block_id), None)
        if blk is not None and blk.area_m2 > 0.0:
            gc_delta = min(100.0 - blk.G_c, green_area / blk.area_m2 * 100.0)
            deltas.setdefault(block_id, {})
            deltas[block_id]["G_c"] = deltas[block_id].get("G_c", 0.0) + gc_delta

    return deltas


def apply_cool_roof(area: AreaModel, change: Change) -> BlockDeltas:
    """Cool-roof delta: increase roof_albedo toward target for the site's block."""
    site = next((s for s in area.sites if s.site_id == change.site_id), None)
    if site is None:
        return {}
    block_id = site.block_id
    if block_id is None:
        return {}
    blk = next((b for b in area.blocks if b.block_id == block_id), None)
    if blk is None:
        return {}
    # Move roof_albedo toward cool_roof_albedo target; never exceed the target
    current = blk.roof_albedo
    target = S.cool_roof_albedo
    delta = max(0.0, target - current)  # only increase albedo
    if delta == 0.0:
        return {}
    return {block_id: {"roof_albedo": delta}}


def collect_deltas(area: AreaModel, changes: Sequence[Change]) -> BlockDeltas:
    """Aggregate attribute deltas from all changes; iterate in sorted site_id order."""
    combined: BlockDeltas = {}
    dispatch = {
        "tree_row": apply_tree_row,
        "shade": apply_shade,
        "depave": apply_depave,
        "pocket_green": apply_pocket_green,
        "cool_roof": apply_cool_roof,
    }
    for change in sorted(changes, key=lambda c: c.site_id):
        fn = dispatch.get(change.kind)
        if fn is None:
            continue
        for block_id, attrs in fn(area, change).items():
            combined.setdefault(block_id, {})
            for attr, delta in attrs.items():
                combined[block_id][attr] = combined[block_id].get(attr, 0.0) + delta
    return combined
