"""Per-block attributes from OSM geometry (the OSM proxy path; Earth Engine layers replace it in bundle v2)."""

from __future__ import annotations

import hashlib
import math
from typing import Any, cast

import geopandas as gpd
import numpy as np
from shapely import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, nearest_points, unary_union
from shapely.strtree import STRtree

from ecozone_engine.model import WaitPointRow
from ecozone_engine.priority import wait_weight_sum

from ..config import AreaConfig, Paths
from ..store import polygonal, read_json, read_table, write_json, write_table
from .geometry import bearing_deg
from .osm import bbox_polygon

PAVED_PUBLIC_LAND = ("parking", "traffic_island")
PROXY = "osm_proxy"


def split_for(block_id: str, seed: str) -> str:
    """Deterministic tune/test half of the blocks (PLANNING.md, Trust and evaluation)."""
    digest = hashlib.sha256(f"{seed}:{block_id}".encode()).hexdigest()
    return "tune" if int(digest[:8], 16) % 2 == 0 else "test"


def axis_mean_deg(bearings: np.ndarray, weights: np.ndarray) -> float:
    """Length-weighted mean of line orientations (0 to 180); a bearing and its reverse count as one axis."""
    rad = np.radians(bearings)
    s = float(np.sum(weights * np.sin(2 * rad)))
    c = float(np.sum(weights * np.cos(2 * rad)))
    return float(math.degrees(math.atan2(s, c)) / 2 % 180)


def long_axis_deg(geom: BaseGeometry) -> float:
    """Orientation (0 to 180) of the longer side of a block's minimum rotated rectangle."""
    pts = list(geom.minimum_rotated_rectangle.exterior.coords)
    sides = [(pts[i], pts[i + 1]) for i in range(2)]
    a, b = max(sides, key=lambda s: math.dist(s[0], s[1]))
    return bearing_deg((a[0], a[1]), (b[0], b[1])) % 180


def share(geom: BaseGeometry, window: BaseGeometry) -> float:
    """Percent of `window` covered by `geom`."""
    return 100.0 * float(geom.intersection(window).area) / float(window.area) if window.area > 0 else 0.0


def longest_built_run(centre: Point, wind_from_deg: float, half_m: float, built: BaseGeometry) -> float:
    """Longest unbroken stretch of building along the wind line, within `half_m` either side of `centre`."""
    rad = math.radians(wind_from_deg)
    dx, dy = math.sin(rad) * half_m, math.cos(rad) * half_m
    line = LineString([(centre.x - dx, centre.y - dy), (centre.x + dx, centre.y + dy)])
    hit = line.intersection(built)
    if hit.is_empty:
        return 0.0
    pieces = [hit] if isinstance(hit, LineString) else list(getattr(hit, "geoms", []))
    lines = [p for p in pieces if isinstance(p, LineString)]
    if not lines:
        return 0.0
    merged = linemerge(lines)
    parts = [merged] if isinstance(merged, LineString) else list(merged.geoms)
    return max(p.length for p in parts)


def nearest_upwind(
    block: BaseGeometry, targets: list[BaseGeometry], wind_from_deg: float, half_angle_deg: float, cap_m: float
) -> float:
    """Distance to the nearest target lying within the upwind wedge; `cap_m` when there is none."""
    centre = block.centroid
    best = cap_m
    for target in targets:
        near = nearest_points(centre, target)[1]
        if near.distance(centre) == 0:
            return 0.0
        brg = bearing_deg((centre.x, centre.y), (near.x, near.y))
        diff = abs((brg - wind_from_deg + 180) % 360 - 180)
        if diff <= half_angle_deg:
            best = min(best, block.distance(target))
    return float(min(best, cap_m))


def block_attributes(
    blocks: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
    chunks: gpd.GeoDataFrame,
    layers: dict[str, gpd.GeoDataFrame],
    wind_from_deg: float,
    cfg: AreaConfig,
) -> gpd.GeoDataFrame:
    a = cfg["attributes"]
    box = bbox_polygon(cfg)
    green_r, wide_r = float(a["green_buffer_m"]), float(a["wide_green_buffer_m"])

    crowns = unary_union([Point(p).buffer(float(a["tree_crown_radius_m"])) for p in layers["trees"].geometry])
    patches = [g for g in layers["green"].geometry if g.area >= float(a["green_patch_min_m2"])]
    green_u = polygonal(unary_union([*layers["green"].geometry, crowns]))
    roads = layers["roads"]
    surface = unary_union(
        [g.buffer(w / 2, cap_style="flat") for g, w in zip(roads.geometry, roads["width_m"], strict=True)]
    )
    paved_land = layers["public_land"][layers["public_land"]["kind"].isin(PAVED_PUBLIC_LAND)]
    footprints = unary_union(buildings.geometry.tolist()) if len(buildings) else Polygon()
    paved_u = polygonal(unary_union([footprints, surface, *paved_land.geometry])).difference(green_u)
    built_run = footprints.buffer(float(a["l_built_gap_m"]))
    water_targets = [g for g in layers["water"].geometry]
    upwind_targets = [*patches, *water_targets]
    cap = float(a["d_water_cap_m"])
    green_cap = float(a["d_green_cap_m"])
    seed = str(cfg["classify"]["split_seed"])

    b_tree = STRtree(buildings.geometry.values) if len(buildings) else None
    b_foot = buildings["footprint_m2"].to_numpy(dtype=float) if len(buildings) else np.array([])
    b_alb = buildings["roof_albedo"].to_numpy(dtype=float) if len(buildings) else np.array([])
    wait_point_rows: list[WaitPointRow] = (
        [
            WaitPointRow(
                wait_id=str(row.id),
                geometry=row.geometry,
                kind=str(row.kind),
                weight=float(row.weight),
            )
            for row in layers["wait_points"].itertuples(index=False)
        ]
        if len(layers["wait_points"])
        else []
    )
    default_albedo = float(cfg["roof_albedo"]["other"])
    by_block = {bid: grp for bid, grp in chunks.groupby("block_id")}
    bld_by_block = {bid: grp for bid, grp in buildings.groupby("block_id")}

    out = blocks.copy()
    cols: dict[str, list[Any]] = {
        k: []
        for k in (
            "I_s", "G_c", "G_buf", "d_green", "d_water", "H_W", "canyon_axis_deg", "L_built", "V",
            "roof_albedo", "wait_weight", "split", "canyon_axis_source",
        )
    }  # fmt: skip
    for blk in blocks.itertuples(index=False):
        geom = cast(BaseGeometry, blk.geometry)
        win = geom.buffer(green_r).intersection(box)
        wide = geom.buffer(wide_r).intersection(box)
        cols["I_s"].append(min(100.0, share(paved_u, win)))
        cols["G_c"].append(min(100.0, share(green_u, win)))
        cols["G_buf"].append(min(100.0, share(green_u, wide)))
        cols["d_green"].append(min(green_cap, float(min((geom.distance(p) for p in patches), default=green_cap))))
        cols["d_water"].append(
            nearest_upwind(geom, upwind_targets, wind_from_deg, float(a["upwind_half_angle_deg"]), cap)
        )

        mine = by_block.get(blk.id)
        if mine is not None and len(mine):
            w = mine["length_m"].to_numpy(dtype=float)
            cols["H_W"].append(float(np.average(mine["H_W"].to_numpy(dtype=float), weights=w)))
            cols["canyon_axis_deg"].append(axis_mean_deg(mine["bearing_deg"].to_numpy(dtype=float), w))
            cols["canyon_axis_source"].append("chunks")
        else:
            cols["H_W"].append(0.0)
            cols["canyon_axis_deg"].append(long_axis_deg(geom))
            cols["canyon_axis_source"].append("block_shape")
        cols["L_built"].append(
            longest_built_run(geom.centroid, wind_from_deg, float(a["l_built_half_length_m"]), built_run)
        )

        inside = bld_by_block.get(blk.id)
        cols["V"].append(float((inside["footprint_m2"] * inside["height_m"]).sum()) if inside is not None else 0.0)

        if b_tree is not None:
            hit = b_tree.query(win, predicate="intersects")
            cols["roof_albedo"].append(
                float(np.average(b_alb[hit], weights=b_foot[hit])) if len(hit) else default_albedo
            )
        else:
            cols["roof_albedo"].append(default_albedo)

        cols["wait_weight"].append(wait_weight_sum(geom, wait_point_rows))
        cols["split"].append(split_for(str(blk.id), seed))

    for name, values in cols.items():
        out[name] = values
    for name in ("i_s", "g_c", "g_buf", "d_green", "d_water"):
        out[f"{name}_source"] = PROXY
    out["roof_albedo_source"] = "typology_default"
    out["h_w_source"] = "chunks"
    return out


def v_ref(blocks: gpd.GeoDataFrame, percentile: float) -> float:
    volumes = blocks.loc[blocks["V"] > 0, "V"].to_numpy(dtype=float)
    return float(np.percentile(volumes, percentile)) if len(volumes) else 0.0


def run(cfg: AreaConfig, paths: Paths) -> dict[str, Any]:
    layers = {
        name: read_table(paths.table(f"osm_{name}"))
        for name in ("green", "water", "trees", "roads", "public_land", "wait_points")
    }
    wind = read_json(paths.json("sun_wind"))
    blocks = block_attributes(
        read_table(paths.table("blocks_class")),
        read_table(paths.table("buildings_class")),
        read_table(paths.table("chunks")),
        layers,
        float(wind["wind_from_deg"]),
        cfg,
    )
    write_table(blocks, paths.table("blocks"))
    summary = {
        "blocks": len(blocks),
        "v_ref": v_ref(blocks, float(cfg["attributes"]["v_ref_percentile"])),
        "canyon_axis_from_block_shape": int((blocks["canyon_axis_source"] == "block_shape").sum()),
        "tune_blocks": int((blocks["split"] == "tune").sum()),
        "test_blocks": int((blocks["split"] == "test").sum()),
    }
    write_json(summary, paths.json("attributes"))
    return summary
