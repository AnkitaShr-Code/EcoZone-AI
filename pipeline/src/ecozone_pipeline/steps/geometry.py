"""Blocks, footpath runs and 10 m chunks, road widths and street H/W (pipeline/RULES.md, DESIGN.md C1)."""

from __future__ import annotations

import itertools
import math
from collections import Counter, defaultdict
from typing import Any, cast

import geopandas as gpd
import numpy as np
import shapely
from shapely import LineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, polygonize, substring, unary_union
from shapely.strtree import STRtree

from ..config import AreaConfig, Paths
from ..store import polygonal, read_table, write_json, write_table
from .osm import bbox_polygon, iter_polygons

VERTEX_DECIMALS = 2
CHUNK_COLUMNS = [
    "id", "geometry", "run_id", "block_id", "road_name", "road_class", "road_width_m", "width_source",
    "bearing_deg", "side", "length_m", "H_W", "near_wait", "footpath_source",
]  # fmt: skip


def bearing_deg(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Compass bearing from a to b in degrees clockwise from north, 0 to 360."""
    return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 360


# ---------- blocks ----------


def build_blocks(roads: gpd.GeoDataFrame, cfg: AreaConfig) -> gpd.GeoDataFrame:
    """Faces of the road network (plus the area box) with the road surface taken out."""
    box = bbox_polygon(cfg)
    flat = roads[~roads["grade_separated"].astype(bool)]
    network = unary_union([*flat.geometry.tolist(), box.exterior])
    faces = [f for f in polygonize(network) if box.buffer(0.01).contains(f.representative_point())]
    surface = unary_union(
        [g.buffer(w / 2, cap_style="flat") for g, w in zip(flat.geometry, flat["width_m"], strict=True)]
    )
    min_area = float(cfg["geometry"]["min_block_area_m2"])
    pieces: list[Any] = []
    for face in faces:
        for poly in iter_polygons(polygonal(face.difference(surface))):
            if poly.area >= min_area:
                pieces.append(poly)
    pieces.sort(key=lambda p: (round(p.centroid.x), round(p.centroid.y)))
    return gpd.GeoDataFrame(
        {
            "id": [f"blk_{i + 1:04d}" for i in range(len(pieces))],
            "area_m2": [p.area for p in pieces],
        },
        geometry=pieces,
        crs=cfg.crs,
    )


# ---------- road edges and junctions ----------


def _vertex(xy: tuple[float, float]) -> tuple[float, float]:
    return (round(xy[0], VERTEX_DECIMALS), round(xy[1], VERTEX_DECIMALS))


def split_roads(roads: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Split each road at vertices it shares with another road, so every edge runs between junction candidates."""
    ways_at: dict[tuple[float, float], set[str]] = defaultdict(set)
    for rid, geom in zip(roads["id"], roads.geometry, strict=True):
        for xy in cast(LineString, geom).coords:
            ways_at[_vertex((xy[0], xy[1]))].add(rid)

    rows: list[dict[str, Any]] = []
    for rec in roads.itertuples(index=False):
        coords = [(c[0], c[1]) for c in cast(LineString, rec.geometry).coords]
        cut = [0]
        for i in range(1, len(coords) - 1):
            if len(ways_at[_vertex(coords[i])]) > 1:
                cut.append(i)
        cut.append(len(coords) - 1)
        for k, (a, b) in enumerate(itertools.pairwise(cut)):
            line = LineString(coords[a : b + 1])
            if line.length <= 0:
                continue
            rows.append(
                {
                    "id": f"e_{rec.id}_{k}",
                    "geometry": line,
                    "road_id": rec.id,
                    "road_class": rec.road_class,
                    "name": rec.name,
                    "width_m": rec.width_m,
                    "width_source": rec.width_source,
                    "start": _vertex(coords[a]),
                    "end": _vertex(coords[b]),
                }
            )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=roads.crs)


def junction_zones(edges: gpd.GeoDataFrame, cfg: AreaConfig) -> BaseGeometry:
    """Discs around vertices where three or more edges meet; footpaths are clipped out of them."""
    degree: Counter[tuple[float, float]] = Counter()
    half_width: dict[tuple[float, float], float] = defaultdict(float)
    for start, end, width in zip(edges["start"], edges["end"], edges["width_m"], strict=True):
        for v in (start, end):
            degree[v] += 1
            half_width[v] = max(half_width[v], float(width) / 2)
    clip = float(cfg["geometry"]["junction_clip_m"])
    discs = [Point(v).buffer(clip + half_width[v]) for v, d in sorted(degree.items()) if d >= 3]
    return unary_union(discs) if discs else shapely.Polygon()


# ---------- footpaths ----------


def _lines(geom: BaseGeometry) -> list[LineString]:
    if geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    return [g for part in getattr(geom, "geoms", []) for g in _lines(part)]


def _merged(geom: BaseGeometry) -> list[LineString]:
    parts = _lines(geom)
    if not parts:
        return []
    merged = linemerge(parts)
    return sorted(_lines(merged), key=lambda g: (round(g.centroid.x, 1), round(g.centroid.y, 1)))


def footpath_runs(
    edges: gpd.GeoDataFrame, sidewalks: gpd.GeoDataFrame, zones: BaseGeometry, cfg: AreaConfig
) -> gpd.GeoDataFrame:
    """One line per road edge side: the OSM sidewalk where it covers the derived kerb line, else the derived line."""
    geo = cfg["geometry"]
    match_m = float(geo["sidewalk_match_m"])
    min_cover = float(geo["sidewalk_min_cover"])
    walk = unary_union(sidewalks.geometry.tolist()) if len(sidewalks) else shapely.LineString()
    walk_zone = walk.buffer(match_m) if not walk.is_empty else shapely.Polygon()

    rows: list[dict[str, Any]] = []
    for edge in edges.itertuples(index=False):
        line = cast(LineString, edge.geometry)
        for side, sign in (("left", 1), ("right", -1)):
            derived = line.offset_curve(sign * float(edge.width_m) / 2)
            if derived.is_empty or derived.length <= 0:
                continue
            source = "derived"
            geom: BaseGeometry = derived
            if not walk_zone.is_empty:
                covered = derived.intersection(walk_zone).length / derived.length
                if covered >= min_cover:
                    geom = walk.intersection(derived.buffer(match_m))
                    source = "osm"
            geom = geom.difference(zones) if not zones.is_empty else geom
            for k, part in enumerate(_merged(geom)):
                rows.append(
                    {
                        "run_id": f"run_{edge.id}_{side}_{k}",
                        "geometry": part,
                        "edge_id": edge.id,
                        "side": side,
                        "footpath_source": source,
                    }
                )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=edges.crs)


def chunk_line(line: LineString, length_m: float, min_m: float) -> list[LineString]:
    """Cut a run into pieces of `length_m` from its start; a remainder shorter than `min_m` is dropped."""
    total = line.length
    pieces: list[LineString] = []
    start = 0.0
    while start < total - 1e-9:
        end = min(start + length_m, total)
        if end - start >= min_m:
            piece = substring(line, start, end)
            if isinstance(piece, LineString) and piece.length > 0:
                pieces.append(piece)
        start = end
    return pieces


def build_chunks(
    runs: gpd.GeoDataFrame,
    edges: gpd.GeoDataFrame,
    blocks: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
    wait_points: gpd.GeoDataFrame,
    cfg: AreaConfig,
) -> gpd.GeoDataFrame:
    geo = cfg["geometry"]
    edge_by_id = {r.id: r for r in edges.itertuples(index=False)}
    rows: list[dict[str, Any]] = []
    for run in runs.sort_values("run_id", kind="stable").itertuples(index=False):
        edge = edge_by_id[run.edge_id]
        for piece in chunk_line(
            cast(LineString, run.geometry), float(geo["chunk_length_m"]), float(geo["min_chunk_m"])
        ):
            pts = list(piece.coords)
            mid = piece.interpolate(0.5, normalized=True)
            rows.append(
                {
                    "geometry": piece,
                    "run_id": run.run_id,
                    "edge_id": run.edge_id,
                    "road_name": edge.name,
                    "road_class": edge.road_class,
                    "road_width_m": float(edge.width_m),
                    "bearing_deg": bearing_deg((pts[0][0], pts[0][1]), (pts[-1][0], pts[-1][1])),
                    "side": run.side,
                    "length_m": piece.length,
                    "footpath_source": run.footpath_source,
                    "_mid": mid,
                }
            )
    chunks = gpd.GeoDataFrame(rows, geometry="geometry", crs=runs.crs)
    if chunks.empty:
        return gpd.GeoDataFrame({c: [] for c in CHUNK_COLUMNS}, geometry=gpd.GeoSeries([], crs=runs.crs), crs=runs.crs)
    chunks["id"] = [f"ch_{i + 1:06d}" for i in range(len(chunks))]
    mids = np.array([m for m in chunks["_mid"]], dtype=object)
    chunks = chunks.drop(columns=["_mid"])

    chunks["block_id"] = nearest_block(mids, blocks, float(geo["block_chunk_max_m"]))
    chunks["H_W"] = street_hw(chunks, mids, edges, buildings, float(geo["frontage_m"]))
    chunks["near_wait"] = within_distance(mids, wait_points, float(cfg["wait_points"]["near_wait_m"]))
    chunks["width_source"] = chunks["edge_id"].map(edges.set_index("id")["width_source"])
    return chunks[CHUNK_COLUMNS]


def nearest_block(points: np.ndarray, blocks: gpd.GeoDataFrame, max_m: float) -> list[str | None]:
    if blocks.empty:
        return [None] * len(points)
    tree = STRtree(blocks.geometry.values)
    ids = blocks["id"].to_numpy()
    result: list[str | None] = [None] * len(points)
    found = tree.query_nearest(points, max_distance=max_m, all_matches=False, return_distance=False)
    for pi, bi in zip(found[0], found[1], strict=True):
        result[int(pi)] = str(ids[int(bi)])
    return result


def within_distance(points: np.ndarray, targets: gpd.GeoDataFrame, max_m: float) -> list[bool]:
    if targets.empty:
        return [False] * len(points)
    tree = STRtree(targets.geometry.values)
    near = tree.query(points, predicate="dwithin", distance=max_m)
    flags = np.zeros(len(points), dtype=bool)
    flags[np.unique(near[0])] = True
    return flags.tolist()


def street_hw(
    chunks: gpd.GeoDataFrame,
    mids: np.ndarray,
    edges: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
    frontage_m: float,
) -> list[float]:
    """Mean building height along the street at the chunk, over road width. Zero when no building frames it."""
    if buildings.empty:
        return [0.0] * len(chunks)
    tree = STRtree(buildings.geometry.values)
    heights = buildings["height_m"].to_numpy(dtype=float)
    edge_geom = dict(zip(edges["id"], edges.geometry, strict=True))
    out: list[float] = []
    for mid, edge_id, width in zip(mids, chunks["edge_id"], chunks["road_width_m"], strict=True):
        line = edge_geom[edge_id]
        centre = line.interpolate(line.project(mid))
        hit = tree.query(centre.buffer(float(width) / 2 + frontage_m), predicate="intersects")
        out.append(float(heights[hit].mean() / float(width)) if len(hit) else 0.0)
    return out


def run(cfg: AreaConfig, paths: Paths) -> dict[str, Any]:
    roads = read_table(paths.table("osm_roads"))
    sidewalks = read_table(paths.table("osm_sidewalks"))
    wait_points = read_table(paths.table("osm_wait_points"))
    buildings = read_table(paths.table("heights"))

    blocks = build_blocks(roads, cfg)
    edges = split_roads(roads)
    zones = junction_zones(edges, cfg)
    runs = footpath_runs(edges, sidewalks, zones, cfg)
    chunks = build_chunks(runs, edges, blocks, buildings, wait_points, cfg)

    write_table(blocks, paths.table("blocks_geom"))
    write_table(edges.drop(columns=["start", "end"]), paths.table("edges"))
    write_table(chunks, paths.table("chunks"))
    summary = {
        "blocks": len(blocks),
        "edges": len(edges),
        "chunks": len(chunks),
        "chunks_derived_footpath": int((chunks["footpath_source"] == "derived").sum()),
        "chunks_osm_sidewalk": int((chunks["footpath_source"] == "osm").sum()),
        "chunks_width_from_road_class": int((chunks["width_source"] == "road_class").sum()),
        "chunks_without_block": int(chunks["block_id"].isna().sum()),
    }
    write_json(summary, paths.json("geometry"))
    return summary
