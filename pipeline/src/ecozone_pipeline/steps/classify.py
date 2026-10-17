"""Building-to-block assignment, built-form class, Protect parcels and Repair candidate sites."""

from __future__ import annotations

import math
from typing import Any, cast

import geopandas as gpd
import numpy as np
import shapely
from shapely import LineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..config import AreaConfig, Paths
from ..store import polygonal, read_table, text, write_json, write_table
from .geometry import bearing_deg
from .osm import iter_polygons

# PLANNING.md, intervention library: how long each type takes to help.
TIME_TO_BENEFIT = {
    "tree_row": "years",
    "shade": "weeks",
    "depave": "season",
    "pocket_green": "years",
    "cool_roof": "weeks",
}
SITE_KINDS = ("tree_row", "shade", "depave", "pocket_green", "cool_roof")
PUBLIC_LAND_LABEL = {"school_grounds": "School grounds", "parking": "Parking lot", "traffic_island": "Traffic island"}


# ---------- buildings and blocks ----------


def assign_blocks(buildings: gpd.GeoDataFrame, blocks: gpd.GeoDataFrame, max_m: float) -> list[str | None]:
    """Block with the largest overlap; else the nearest block within `max_m`; else None."""
    result: list[str | None] = [None] * len(buildings)
    if blocks.empty or buildings.empty:
        return result
    tree = STRtree(blocks.geometry.values)
    block_ids = blocks["id"].to_numpy()
    geoms = buildings.geometry.values
    pairs = tree.query(geoms, predicate="intersects")
    best: dict[int, tuple[float, int]] = {}
    for bi, ki in zip(pairs[0], pairs[1], strict=True):
        overlap = float(shapely.intersection(geoms[bi], blocks.geometry.values[ki]).area)
        cur = best.get(int(bi))
        if cur is None or overlap > cur[0] or (overlap == cur[0] and int(ki) < cur[1]):
            best[int(bi)] = (overlap, int(ki))
    for bi, (_, ki) in best.items():
        result[bi] = str(block_ids[ki])
    missing = [i for i, r in enumerate(result) if r is None]
    if missing:
        found = tree.query_nearest(
            [geoms[i] for i in missing], max_distance=max_m, all_matches=False, return_distance=False
        )
        for mi, ki in zip(found[0], found[1], strict=True):
            result[missing[int(mi)]] = str(block_ids[int(ki)])
    return result


def classify_blocks(blocks: gpd.GeoDataFrame, buildings: gpd.GeoDataFrame, cfg: AreaConfig) -> gpd.GeoDataFrame:
    """Coverage, median footprint and floors, and the built-form class per block (PLANNING.md, Repair priority)."""
    rule = cfg["dense_low_rise"]
    per_floor = float(cfg["osm"]["metres_per_floor"])
    out = blocks.copy()
    grouped = buildings.groupby("block_id")
    footprint_sum = grouped["footprint_m2"].sum()
    footprint_median = grouped["footprint_m2"].median()
    floors_median = grouped["height_m"].median() / per_floor
    out["building_count"] = out["id"].map(grouped.size()).fillna(0).astype(int)
    out["coverage"] = (out["id"].map(footprint_sum).fillna(0.0) / out["area_m2"]).clip(upper=1.0)
    out["median_footprint_m2"] = out["id"].map(footprint_median).fillna(0.0)
    out["median_floors"] = out["id"].map(floors_median).fillna(0.0)
    dense = (
        (out["coverage"] >= float(rule["min_coverage"]))
        & (out["median_footprint_m2"] <= float(rule["max_median_footprint_m2"]))
        & (out["median_floors"] <= float(rule["max_median_floors"]))
        & (out["building_count"] > 0)
    )
    out["built_form"] = np.where(dense, "dense_low_rise", "other")
    return out


# ---------- open land ----------


def open_spaces(
    blocks: gpd.GeoDataFrame,
    obstacles: BaseGeometry,
    *,
    buffer_m: float,
    opening_m: float,
    min_area_m2: float,
    max_area_m2: float,
) -> gpd.GeoDataFrame:
    """Unbuilt, ungreen land in each block, with slivers removed by a morphological opening."""
    rows: list[dict[str, Any]] = []
    blocked = obstacles.buffer(buffer_m) if buffer_m > 0 else obstacles
    for block in blocks.itertuples(index=False):
        free = polygonal(cast(BaseGeometry, block.geometry).difference(blocked))
        if free.is_empty:
            continue
        opened = polygonal(free.buffer(-opening_m).buffer(opening_m))
        for poly in iter_polygons(opened):
            if min_area_m2 <= poly.area <= max_area_m2:
                rows.append({"block_id": block.id, "geometry": poly, "area_m2": poly.area})
    rows.sort(key=lambda r: (round(r["geometry"].centroid.x), round(r["geometry"].centroid.y)))
    return (
        gpd.GeoDataFrame(rows, geometry="geometry", crs=blocks.crs)
        if rows
        else _empty(blocks.crs, ["block_id", "area_m2"])
    )


def _empty(crs: Any, columns: list[str]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({c: [] for c in columns}, geometry=gpd.GeoSeries([], crs=crs), crs=crs)


def nearest_index(tree: STRtree, geom: BaseGeometry, max_m: float | None = None) -> int | None:
    hit = tree.query_nearest(geom, max_distance=max_m, all_matches=False)
    return int(hit[0]) if len(hit) else None


# ---------- parcels (Protect) ----------


def nearest_edge(geom: BaseGeometry, edges: gpd.GeoDataFrame, max_m: float) -> tuple[Any, float] | None:
    """The nearest road edge within `max_m` and the street bearing (axis, 0 to 180) beside `geom`."""
    if edges.empty:
        return None
    tree = STRtree(edges.geometry.values)
    idx = nearest_index(tree, geom, max_m)
    if idx is None:
        return None
    edge = edges.iloc[idx]
    line = cast(LineString, edge.geometry)
    d = line.project(geom.centroid)
    a, b = line.interpolate(max(d - 5, 0)), line.interpolate(min(d + 5, line.length))
    return edge, bearing_deg((a.x, a.y), (b.x, b.y)) % 180


def build_parcels(
    blocks: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
    obstacles: BaseGeometry,
    vacant: gpd.GeoDataFrame,
    edges: gpd.GeoDataFrame,
    cfg: AreaConfig,
) -> gpd.GeoDataFrame:
    c = cfg["classify"]
    low_cover = blocks[blocks["coverage"] <= float(c["max_coverage_for_parcel"])]
    free = open_spaces(
        low_cover,
        obstacles,
        buffer_m=float(c["parcel_open_buffer_m"]),
        opening_m=float(c["parcel_opening_m"]),
        min_area_m2=float(c["min_parcel_m2"]),
        max_area_m2=float(c["max_parcel_m2"]),
    )
    candidates: list[dict[str, Any]] = [
        {"geometry": g, "block_id": b, "vacant_tag": False, "name": None}
        for g, b in zip(free.geometry, free["block_id"], strict=True)
    ]
    if len(vacant) and len(blocks):
        tree = STRtree(blocks.geometry.values)
        for rec in vacant.itertuples(index=False):
            if not (float(c["min_parcel_m2"]) <= rec.geometry.area <= float(c["max_parcel_m2"])):
                continue
            idx = nearest_index(tree, rec.geometry)
            candidates.append(
                {
                    "geometry": rec.geometry,
                    "block_id": str(blocks["id"].iloc[idx]),
                    "vacant_tag": True,
                    "name": text(rec.name),
                }
            )

    b_tree = STRtree(buildings.geometry.values) if len(buildings) else None
    b_height = buildings["height_m"].to_numpy(dtype=float) if len(buildings) else np.array([])
    rows: list[dict[str, Any]] = []
    for cand in candidates:
        geom = cand["geometry"]
        found = nearest_edge(geom, edges, float(c["parcel_road_max_m"]))
        if found is None:
            continue
        edge, axis = found
        near = b_tree.query(geom.buffer(float(c["neighbour_radius_m"])), predicate="intersects") if b_tree else []
        rows.append(
            {
                **cand,
                "area_m2": geom.area,
                "road_name": text(edge.name),
                "road_width_m": float(edge.width_m),
                "street_bearing_deg": float(axis),
                "neighbour_height_m": float(b_height[near].mean()) if len(near) else 0.0,
            }
        )
    rows.sort(
        key=lambda r: (
            not r["vacant_tag"],
            -r["area_m2"],
            round(r["geometry"].centroid.x),
            round(r["geometry"].centroid.y),
        )
    )
    rows = rows[: int(c["max_parcels"])]
    rows.sort(key=lambda r: (round(r["geometry"].centroid.x), round(r["geometry"].centroid.y)))
    for i, r in enumerate(rows):
        r["id"] = f"pc_{i + 1:03d}"
        r["name"] = r["name"] or f"Open plot on {r['road_name'] or 'an unnamed lane'}"
    columns = [
        "id", "block_id", "area_m2", "road_name", "road_width_m", "street_bearing_deg",
        "neighbour_height_m", "vacant_tag", "name",
    ]  # fmt: skip
    if not rows:
        return _empty(blocks.crs, columns)
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=blocks.crs)[[*columns, "geometry"]]


# ---------- sites (Repair) ----------


def _joins(previous: Any, current: Any, tolerance_m: float = 0.5) -> bool:
    """True when two consecutive chunks of a run touch end to start (within tolerance)."""
    return bool(previous.distance(current) <= tolerance_m)


def tree_row_sites(chunks: gpd.GeoDataFrame, cfg: AreaConfig) -> list[dict[str, Any]]:
    s = cfg["sites"]["tree_row"]
    rows: list[dict[str, Any]] = []
    eligible = chunks[chunks["road_width_m"] >= float(s["min_road_width_m"])]
    for run_id, run in eligible.groupby("run_id", sort=True):
        group: list[Any] = []
        length = 0.0

        def flush(run_id: str = str(run_id), group: list[Any] = group) -> None:
            glen = sum(c.length_m for c in group)
            trees = math.floor(glen / float(s["spacing_m"]))
            if trees < int(s["min_trees"]):
                return
            # The site rule is per street: one deep stretch rejects the whole row, so use the worst chunk.
            hw = float(max(c.H_W for c in group))
            geom = shapely.line_merge(shapely.multilinestrings([c.geometry for c in group]))
            first = group[0]
            rejected = hw >= float(s["canopy_hw_limit"])
            rows.append(
                {
                    "kind": "tree_row",
                    "geometry": geom,
                    "name": f"{text(first.road_name) or 'Unnamed lane'}, {first.side} footpath",
                    "quantity_min": float(s["min_trees"]),
                    "quantity_max": float(trees),
                    "rule": "CANOPY_OBSTRUCTION" if rejected else "tree_row_strip",
                    "rejected": rejected,
                    "wait_point_id": None,
                    "H_W": hw,
                    "block_id": first.block_id,
                }
            )

        for chunk in run.itertuples(index=False):
            if group and not _joins(group[-1].geometry, chunk.geometry):
                # A gap in the run would make the merged row a MultiLineString, which the API cannot serve.
                flush()
                group.clear()
                length = 0.0
            group.append(chunk)
            length += chunk.length_m
            if length >= float(s["max_run_length_m"]):
                flush()
                group.clear()
                length = 0.0
        if group:
            flush()
    return rows


def shade_sites(chunks: gpd.GeoDataFrame, wait_points: gpd.GeoDataFrame, cfg: AreaConfig) -> list[dict[str, Any]]:
    s = cfg["sites"]["shade"]
    near_m = float(cfg["wait_points"]["near_wait_m"])
    if chunks.empty or wait_points.empty:
        return []
    tree = STRtree(chunks.geometry.values)
    rows: list[dict[str, Any]] = []
    for wp in wait_points.sort_values("id", kind="stable").itertuples(index=False):
        idx = nearest_index(tree, wp.geometry, near_m)
        if idx is None:
            continue
        chunk = chunks.iloc[idx]
        line = cast(LineString, chunk.geometry)
        pt = line.interpolate(line.project(wp.geometry))
        label = text(wp.name) or wp.kind.replace("_", " ")
        rows.append(
            {
                "kind": "shade",
                "geometry": pt.buffer(float(s["structure_half_width_m"]), cap_style="square"),
                "name": f"Shade at {label}",
                "quantity_min": float(s["min_m2"]),
                "quantity_max": float(s["max_m2"]),
                "rule": "shade_near_wait_point",
                "rejected": False,
                "wait_point_id": wp.id,
                "H_W": float(chunk.H_W),
                "block_id": chunk.block_id,
            }
        )
    return rows


def depave_sites(
    public_land: gpd.GeoDataFrame,
    buildings: BaseGeometry,
    green: BaseGeometry,
    blocks: gpd.GeoDataFrame,
    cfg: AreaConfig,
) -> list[dict[str, Any]]:
    s = cfg["sites"]["depave"]
    rows: list[dict[str, Any]] = []
    block_tree = STRtree(blocks.geometry.values) if len(blocks) else None
    for land in public_land.sort_values("id", kind="stable").itertuples(index=False):
        paved = polygonal(cast(BaseGeometry, land.geometry).difference(buildings.buffer(1)).difference(green))
        for poly in iter_polygons(paved):
            if poly.area < float(s["min_area_m2"]):
                continue
            block = None
            if block_tree is not None:
                idx = nearest_index(block_tree, poly)
                block = str(blocks["id"].iloc[idx]) if idx is not None else None
            label = PUBLIC_LAND_LABEL.get(land.kind, land.kind)
            land_name = text(land.name)
            rows.append(
                {
                    "kind": "depave",
                    "geometry": poly,
                    "name": f"{label}: {land_name}" if land_name else label,
                    "quantity_min": round(poly.area * float(s["min_share"]), 1),
                    "quantity_max": round(poly.area * float(s["max_share"]), 1),
                    "rule": f"depave_{land.kind}",
                    "rejected": False,
                    "wait_point_id": None,
                    "H_W": None,
                    "block_id": block,
                }
            )
    return rows


def pocket_green_sites(open_land: gpd.GeoDataFrame, vacant: gpd.GeoDataFrame, cfg: AreaConfig) -> list[dict[str, Any]]:
    s = cfg["sites"]["pocket_green"]
    cands: list[tuple[BaseGeometry, str | None, str | None, str]] = [
        (g, b, None, "pocket_green_open_plot") for g, b in zip(open_land.geometry, open_land["block_id"], strict=True)
    ]
    cands += [
        (g, None, text(n), "pocket_green_vacant_plot") for g, n in zip(vacant.geometry, vacant["name"], strict=True)
    ]
    cands = [c for c in cands if float(s["min_area_m2"]) <= c[0].area <= float(s["max_area_m2"])]
    cands.sort(key=lambda c: (-c[0].area, round(c[0].centroid.x), round(c[0].centroid.y)))
    rows: list[dict[str, Any]] = []
    for geom, block, name, rule in cands[: int(s["max_sites"])]:
        rows.append(
            {
                "kind": "pocket_green",
                "geometry": geom,
                "name": name or "Open plot",
                "quantity_min": round(geom.area * float(s["min_share"]), 1),
                "quantity_max": round(geom.area * float(s["max_share"]), 1),
                "rule": rule,
                "rejected": False,
                "wait_point_id": None,
                "H_W": None,
                "block_id": block,
            }
        )
    return rows


def cool_roof_sites(blocks: gpd.GeoDataFrame, buildings: gpd.GeoDataFrame, cfg: AreaConfig) -> list[dict[str, Any]]:
    s = cfg["sites"]["cool_roof"]
    rows: list[dict[str, Any]] = []
    dark = buildings[buildings["roof_albedo"] <= float(s["max_albedo"])]
    for block in (
        blocks[blocks["built_form"] == "dense_low_rise"].sort_values("id", kind="stable").itertuples(index=False)
    ):
        roofs = dark[dark["block_id"] == block.id]
        if roofs.empty:
            continue
        geom = unary_union(roofs.geometry.tolist())
        area = float(roofs["footprint_m2"].sum())
        rows.append(
            {
                "kind": "cool_roof",
                "geometry": geom if isinstance(geom, (Polygon, MultiPolygon)) else polygonal(geom),
                "name": f"Dark roofs, block {block.id}",
                "quantity_min": round(area * float(s["min_share"]), 1),
                "quantity_max": round(area * float(s["max_share"]), 1),
                "rule": "cool_roof_dense_low_rise",
                "rejected": False,
                "wait_point_id": None,
                "H_W": None,
                "block_id": block.id,
            }
        )
    return rows


def assemble_sites(parts: list[list[dict[str, Any]]], crs: Any) -> gpd.GeoDataFrame:
    rows = [r for part in parts for r in part]
    columns = [
        "id", "kind", "name", "quantity_min", "quantity_max", "rule", "rejected", "wait_point_id",
        "H_W", "block_id", "time_to_benefit",
    ]  # fmt: skip
    if not rows:
        return _empty(crs, columns)
    order = {k: i for i, k in enumerate(SITE_KINDS)}
    rows.sort(
        key=lambda r: (order[r["kind"]], round(r["geometry"].centroid.x), round(r["geometry"].centroid.y), r["name"])
    )
    for i, r in enumerate(rows):
        r["id"] = f"s_{i + 1:04d}"
        r["time_to_benefit"] = TIME_TO_BENEFIT[r["kind"]]
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=crs)[[*columns, "geometry"]]


def run(cfg: AreaConfig, paths: Paths) -> dict[str, Any]:
    geo = cfg["geometry"]
    blocks = read_table(paths.table("blocks_geom"))
    chunks = read_table(paths.table("chunks"))
    edges = read_table(paths.table("edges"))
    buildings = read_table(paths.table("heights"))
    wait_points = read_table(paths.table("osm_wait_points"))
    green = read_table(paths.table("osm_green"))
    water = read_table(paths.table("osm_water"))
    public_land = read_table(paths.table("osm_public_land"))
    vacant = read_table(paths.table("osm_vacant"))

    buildings["block_id"] = assign_blocks(buildings, blocks, float(geo["block_chunk_max_m"]))
    blocks = classify_blocks(blocks, buildings, cfg)

    footprints = unary_union(buildings.geometry.tolist()) if len(buildings) else Polygon()
    green_u = unary_union(green.geometry.tolist()) if len(green) else Polygon()
    water_u = unary_union(water.geometry.tolist()) if len(water) else Polygon()
    land_u = unary_union(public_land.geometry.tolist()) if len(public_land) else Polygon()
    obstacles = unary_union([footprints, green_u, water_u, land_u])

    parcels = build_parcels(blocks, buildings, obstacles, vacant, edges, cfg)
    pocket = cfg["sites"]["pocket_green"]
    pocket_open = open_spaces(
        blocks,
        obstacles,
        buffer_m=float(pocket["open_buffer_m"]),
        opening_m=float(pocket["opening_m"]),
        min_area_m2=float(pocket["min_area_m2"]),
        max_area_m2=float(pocket["max_area_m2"]),
    )
    sites = assemble_sites(
        [
            tree_row_sites(chunks, cfg),
            shade_sites(chunks, wait_points, cfg),
            depave_sites(public_land, footprints, green_u, blocks, cfg),
            pocket_green_sites(pocket_open, vacant, cfg),
            cool_roof_sites(blocks, buildings, cfg),
        ],
        blocks.crs,
    )

    write_table(buildings, paths.table("buildings_class"))
    write_table(blocks, paths.table("blocks_class"))
    write_table(parcels, paths.table("parcels"))
    write_table(sites, paths.table("sites"))
    summary = {
        "parcels": len(parcels),
        "sites_by_kind": {k: int((sites["kind"] == k).sum()) for k in SITE_KINDS},
        "sites_rejected_canopy": int((sites["rule"] == "CANOPY_OBSTRUCTION").sum()),
        "blocks_dense_low_rise": int((blocks["built_form"] == "dense_low_rise").sum()),
        "buildings_without_block": int(buildings["block_id"].isna().sum()),
    }
    write_json(summary, paths.json("classify"))
    return summary
