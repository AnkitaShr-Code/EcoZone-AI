"""OSM extract: buildings, roads, sidewalks, green, water, waiting points, public land (pipeline/RULES.md)."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any, cast

import geopandas as gpd
import httpx
import numpy as np
import shapely
from shapely import LineString, MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, polygonize

from ..config import AreaConfig, Paths
from ..store import polygonal, read_json, write_json, write_table

Element = Mapping[str, Any]

GREEN_LEISURE = ("park", "garden", "recreation_ground", "nature_reserve", "common")
GREEN_LANDUSE = ("grass", "forest", "meadow", "village_green", "recreation_ground")
GREEN_NATURAL = ("wood", "scrub", "grassland")
WATER_WATERWAY = ("river", "stream", "canal", "riverbank")
WAIT_AMENITIES = ("school", "college", "hospital", "clinic", "marketplace")
PUBLIC_LAND_AMENITIES = ("parking", "school", "college")
VACANT_LANDUSE = ("brownfield", "greenfield", "construction")

TABLES = (
    "buildings",
    "roads",
    "sidewalks",
    "green",
    "water",
    "wait_points",
    "public_land",
    "vacant",
    "trees",
)


def overpass_query(cfg: AreaConfig) -> str:
    w, s, e, n = cfg.bbox_wgs84
    b = f"{s},{w},{n},{e}"
    classes = "|".join(cfg["osm"]["road_classes"] + [f"{c}_link" for c in cfg["osm"]["road_classes"][:4]])
    return f"""[out:json][timeout:{cfg["osm"]["timeout_s"]}];
(
  way["building"]({b});
  relation["building"]["type"="multipolygon"]({b});
  way["highway"~"^({classes})$"]({b});
  way["highway"="footway"]["footway"="sidewalk"]({b});
  nwr["leisure"~"^({"|".join(GREEN_LEISURE)})$"]({b});
  nwr["landuse"~"^({"|".join(GREEN_LANDUSE + VACANT_LANDUSE)})$"]({b});
  nwr["natural"~"^({"|".join(GREEN_NATURAL)}|water)$"]({b});
  way["waterway"~"^({"|".join(WATER_WATERWAY)})$"]({b});
  node["natural"="tree"]({b});
  nwr["amenity"~"^({"|".join((*WAIT_AMENITIES, "parking"))})$"]({b});
  node["highway"="bus_stop"]({b});
  way["area:highway"="traffic_island"]({b});
  way["highway"="traffic_island"]({b});
);
out geom tags;"""


def fetch_overpass(cfg: AreaConfig, paths: Paths, *, refresh: bool = False) -> dict[str, Any]:
    """Download once and cache the raw response with its fetch date; re-fetch only on `refresh`.

    `osm.source_file` (relative to the config) reads a committed response instead, for tests and offline runs.
    """
    source_file = cfg["osm"].get("source_file")
    if source_file:
        return read_json(cfg.base_dir / source_file)
    raw_path = paths.raw / "overpass.json"
    meta_path = paths.raw / "overpass.meta.json"
    if raw_path.exists() and meta_path.exists() and not refresh:
        return read_json(raw_path)
    query = overpass_query(cfg)
    osm = cfg["osm"]
    headers = {"User-Agent": "EcoZoneAI-pipeline/0.1 (AI Builder Cup 2026)", "Accept": "application/json"}
    last: Exception | None = None
    for attempt in range(4):
        try:
            resp = httpx.post(osm["overpass_url"], data={"data": query}, headers=headers, timeout=osm["timeout_s"] + 30)
            if resp.status_code in (429, 502, 503, 504):
                raise httpx.HTTPStatusError("overpass busy", request=resp.request, response=resp)
            resp.raise_for_status()
            data = cast(dict[str, Any], resp.json())
            break
        except httpx.HTTPError as err:
            last = err
            if attempt < 3:
                time.sleep(10 * (attempt + 1))
    else:
        raise RuntimeError(f"Overpass fetch failed: {last}")
    write_json(data, raw_path)
    write_json(
        {
            "source": "OpenStreetMap via Overpass API",
            "url": osm["overpass_url"],
            "licence": osm["attribution"],
            "licence_url": osm["licence_url"],
            "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "osm_base_timestamp": (data.get("osm3s") or {}).get("timestamp_osm_base"),
            "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
            "elements": len(data.get("elements", [])),
        },
        meta_path,
    )
    return data


# ---------- geometry from Overpass elements ----------


def _coords(el: Element) -> list[tuple[float, float]]:
    return [(float(p["lon"]), float(p["lat"])) for p in el.get("geometry", []) if p]


def _way_geometry(el: Element, *, area: bool) -> BaseGeometry | None:
    pts = _coords(el)
    if area and len(pts) >= 4 and pts[0] == pts[-1]:
        poly = Polygon(pts)
        return poly if not poly.is_empty else None
    if not area and len(pts) >= 2:
        return LineString(pts)
    return None


def _relation_polygon(el: Element) -> BaseGeometry | None:
    """Assemble a multipolygon relation from its outer and inner member ways."""
    outers: list[LineString] = []
    inners: list[LineString] = []
    for m in el.get("members", []):
        if m.get("type") != "way" or not m.get("geometry"):
            continue
        pts = [(float(p["lon"]), float(p["lat"])) for p in m["geometry"] if p]
        if len(pts) < 2:
            continue
        (inners if m.get("role") == "inner" else outers).append(LineString(pts))
    if not outers:
        return None
    outer = shapely.union_all(list(polygonize(linemerge(outers))))
    if outer.is_empty:
        return None
    if inners:
        hole = shapely.union_all(list(polygonize(linemerge(inners))))
        outer = outer.difference(hole)
    return polygonal(outer)


def _area_geometry(el: Element) -> BaseGeometry | None:
    if el["type"] == "way":
        return _way_geometry(el, area=True)
    if el["type"] == "relation" and (el.get("tags") or {}).get("type") == "multipolygon":
        return _relation_polygon(el)
    return None


def _point_geometry(el: Element) -> BaseGeometry | None:
    if el["type"] == "node" and "lon" in el:
        return Point(float(el["lon"]), float(el["lat"]))
    geom = _area_geometry(el)
    if geom is not None and not geom.is_empty:
        return geom.representative_point()
    bounds = el.get("bounds")
    if bounds:
        return Point((bounds["minlon"] + bounds["maxlon"]) / 2, (bounds["minlat"] + bounds["maxlat"]) / 2)
    return None


def _float(value: object) -> float:
    """First number in an OSM tag such as '12', '12.5 m' or '9;12'; NaN when there is none."""
    if value is None:
        return float("nan")
    token = str(value).replace(",", ".").split(";")[0].split()[0] if str(value).strip() else ""
    try:
        return float(token)
    except ValueError:
        return float("nan")


def _is_green(tags: Mapping[str, str]) -> str | None:
    if tags.get("leisure") in GREEN_LEISURE:
        return tags["leisure"]
    if tags.get("landuse") in GREEN_LANDUSE:
        return tags["landuse"]
    if tags.get("natural") in GREEN_NATURAL:
        return tags["natural"]
    return None


def _wait_kind(tags: Mapping[str, str]) -> str | None:
    if tags.get("highway") == "bus_stop":
        return "bus_stop"
    return tags["amenity"] if tags.get("amenity") in WAIT_AMENITIES else None


def parse_overpass(osm: Mapping[str, Any], cfg: AreaConfig) -> dict[str, gpd.GeoDataFrame]:
    """Turn an Overpass response into one GeoDataFrame per table, in the area CRS, clipped to the bbox."""
    road_classes = set(cfg["osm"]["road_classes"])
    widths: dict[str, float] = cfg["osm"]["road_width_m"]
    weights: dict[str, float] = cfg["wait_points"]["weights"]
    rows: dict[str, list[dict[str, Any]]] = {name: [] for name in TABLES}

    for el in sorted(osm.get("elements", []), key=lambda e: (e["type"], e["id"])):
        tags: Mapping[str, str] = el.get("tags") or {}
        osm_id = f"{el['type'][0]}{el['id']}"

        if "building" in tags and tags["building"] != "no":
            geom = _area_geometry(el)
            if geom is not None:
                rows["buildings"].append(
                    {
                        "id": f"b_{osm_id}",
                        "geometry": geom,
                        "building_tag": tags["building"],
                        "osm_height_m": _float(tags.get("height") or tags.get("building:height")),
                        "osm_levels": _float(tags.get("building:levels")),
                        "name": tags.get("name"),
                    }
                )
            if _wait_kind(tags) is None:
                continue

        highway = tags.get("highway")
        if highway and el["type"] == "way":
            if highway == "footway" and tags.get("footway") == "sidewalk":
                geom = _way_geometry(el, area=False)
                if geom is not None:
                    rows["sidewalks"].append({"id": f"sw_{osm_id}", "geometry": geom})
                continue
            if highway == "traffic_island":
                geom = _way_geometry(el, area=True)
                if geom is not None:
                    rows["public_land"].append(
                        {"id": f"pl_{osm_id}", "geometry": geom, "kind": "traffic_island", "name": tags.get("name")}
                    )
                continue
            cls = highway.removesuffix("_link")
            if cls in road_classes and tags.get("area") != "yes" and "tunnel" not in tags:
                geom = _way_geometry(el, area=False)
                if geom is not None:
                    width = _float(tags.get("width"))
                    rows["roads"].append(
                        {
                            "id": f"r_{osm_id}",
                            "geometry": geom,
                            "road_class": cls,
                            "name": tags.get("name"),
                            "width_m": width if np.isfinite(width) else widths[cls],
                            "width_source": "osm" if np.isfinite(width) else "road_class",
                            "grade_separated": tags.get("bridge", "no") != "no",
                        }
                    )
                continue

        if tags.get("area:highway") == "traffic_island":
            geom = _way_geometry(el, area=True)
            if geom is not None:
                rows["public_land"].append(
                    {"id": f"pl_{osm_id}", "geometry": geom, "kind": "traffic_island", "name": tags.get("name")}
                )
            continue

        if tags.get("natural") == "tree" and el["type"] == "node":
            rows["trees"].append({"id": f"t_{osm_id}", "geometry": _point_geometry(el)})
            continue

        wait = _wait_kind(tags)
        if wait is not None:
            geom = _point_geometry(el)
            if geom is not None:
                rows["wait_points"].append(
                    {
                        "id": f"wp_{osm_id}",
                        "geometry": geom,
                        "kind": wait,
                        "name": tags.get("name"),
                        "weight": float(weights[wait]),
                    }
                )
            if tags.get("amenity") in PUBLIC_LAND_AMENITIES and "building" not in tags:
                grounds = _area_geometry(el)
                if grounds is not None:
                    rows["public_land"].append(
                        {"id": f"pl_{osm_id}", "geometry": grounds, "kind": "school_grounds", "name": tags.get("name")}
                    )
            continue

        if tags.get("amenity") == "parking":
            geom = _area_geometry(el)
            if geom is not None:
                rows["public_land"].append(
                    {"id": f"pl_{osm_id}", "geometry": geom, "kind": "parking", "name": tags.get("name")}
                )
            continue

        water = tags.get("natural") == "water" or tags.get("waterway") in WATER_WATERWAY
        if water:
            geom = _area_geometry(el) if tags.get("waterway") in (None, "riverbank") else _way_geometry(el, area=False)
            if geom is not None:
                rows["water"].append({"id": f"w_{osm_id}", "geometry": geom, "name": tags.get("name")})
            continue

        if tags.get("landuse") in VACANT_LANDUSE:
            geom = _area_geometry(el)
            if geom is not None:
                rows["vacant"].append(
                    {"id": f"v_{osm_id}", "geometry": geom, "kind": tags["landuse"], "name": tags.get("name")}
                )
            continue

        green = _is_green(tags)
        if green is not None:
            geom = _area_geometry(el)
            if geom is not None:
                rows["green"].append({"id": f"g_{osm_id}", "geometry": geom, "kind": green, "name": tags.get("name")})

    return {name: _to_frame(items, name, cfg) for name, items in rows.items()}


_COLUMNS: dict[str, list[str]] = {
    "buildings": ["id", "building_tag", "osm_height_m", "osm_levels", "name"],
    "roads": ["id", "road_class", "name", "width_m", "width_source", "grade_separated"],
    "sidewalks": ["id"],
    "green": ["id", "kind", "name"],
    "water": ["id", "name"],
    "wait_points": ["id", "kind", "name", "weight"],
    "public_land": ["id", "kind", "name"],
    "vacant": ["id", "kind", "name"],
    "trees": ["id"],
}


def _to_frame(items: list[dict[str, Any]], name: str, cfg: AreaConfig) -> gpd.GeoDataFrame:
    crs = cfg.crs
    columns = _COLUMNS[name]
    if not items:
        return gpd.GeoDataFrame({c: [] for c in columns}, geometry=gpd.GeoSeries([], crs=crs), crs=crs)
    gdf = gpd.GeoDataFrame(items, geometry="geometry", crs="EPSG:4326").to_crs(crs)
    gdf = gdf[[*columns, "geometry"]]
    return _clip_to_bbox(gdf, cfg)


def bbox_polygon(cfg: AreaConfig) -> Polygon:
    w, s, e, n = cfg.bbox_wgs84
    box = gpd.GeoSeries([shapely.box(w, s, e, n)], crs="EPSG:4326").to_crs(cfg.crs)
    return cast(Polygon, box.iloc[0])


def _clip_to_bbox(gdf: gpd.GeoDataFrame, cfg: AreaConfig) -> gpd.GeoDataFrame:
    """Clip to the area box, split multipart results, and keep ids unique."""
    box = bbox_polygon(cfg)
    clipped = gdf.copy()
    clipped["geometry"] = clipped.geometry.make_valid().intersection(box)
    clipped = clipped[~clipped.geometry.is_empty].explode(index_parts=False)
    clipped = clipped[clipped.geometry.geom_type != "GeometryCollection"]
    clipped = clipped.sort_values("id", kind="stable").reset_index(drop=True)
    dup = clipped.groupby("id").cumcount()
    clipped["id"] = np.where(dup > 0, clipped["id"] + "_" + dup.astype(str), clipped["id"])
    return clipped


def run(cfg: AreaConfig, paths: Paths, *, refresh: bool = False) -> dict[str, int]:
    osm = fetch_overpass(cfg, paths, refresh=refresh)
    tables = parse_overpass(osm, cfg)
    counts: dict[str, int] = {}
    for name, gdf in tables.items():
        write_table(gdf, paths.table(f"osm_{name}"))
        counts[name] = len(gdf)
    fetch_meta = read_json(paths.raw / "overpass.meta.json") if (paths.raw / "overpass.meta.json").exists() else {}
    write_json({"counts": counts, "fetch": fetch_meta}, paths.json("osm"))
    return counts


def iter_polygons(geom: BaseGeometry) -> Iterable[Polygon]:
    if isinstance(geom, Polygon):
        yield geom
    elif isinstance(geom, MultiPolygon):
        yield from geom.geoms
