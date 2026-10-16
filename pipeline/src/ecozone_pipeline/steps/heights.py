"""Building heights with a source on every row, and the labeled default roof albedo (pipeline/RULES.md)."""

from __future__ import annotations

import math
from typing import Any

import geopandas as gpd
import numpy as np

from ..config import AreaConfig, Paths
from ..store import read_table, write_json, write_table

HEIGHT_SOURCES = ("osm_height", "osm_levels", "open_buildings", "typology")


def typology_floors(building_tag: str, footprint_m2: float, typology: dict[str, Any]) -> int:
    """Default floors for a building with no height information; first matching rule wins."""
    for rule in typology["rules"]:
        tags = rule["building"]
        if tags != "any" and building_tag not in tags:
            continue
        if footprint_m2 > rule.get("max_footprint_m2", math.inf):
            continue
        if footprint_m2 < rule.get("min_footprint_m2", 0):
            continue
        return int(rule["floors"])
    return int(typology["default_floors"])


def assign_heights(buildings: gpd.GeoDataFrame, cfg: AreaConfig) -> gpd.GeoDataFrame:
    """OSM height, then OSM levels x metres per floor, then typology default. Open Buildings needs Earth Engine."""
    per_floor = float(cfg["osm"]["metres_per_floor"])
    albedo = cfg["roof_albedo"]
    out = buildings.copy()
    out["footprint_m2"] = out.geometry.area
    out = out[out["footprint_m2"] >= float(cfg["osm"]["min_building_area_m2"])].reset_index(drop=True)

    height = out["osm_height_m"].to_numpy(dtype=float)
    levels = out["osm_levels"].to_numpy(dtype=float)
    typology_h = np.array(
        [
            typology_floors(str(tag), float(area), cfg["typology"]) * per_floor
            for tag, area in zip(out["building_tag"], out["footprint_m2"], strict=True)
        ]
    )
    has_height = np.isfinite(height) & (height > 0)
    has_levels = ~has_height & np.isfinite(levels) & (levels > 0)
    out["height_m"] = np.where(has_height, height, np.where(has_levels, levels * per_floor, typology_h))
    out["height_source"] = np.where(has_height, "osm_height", np.where(has_levels, "osm_levels", "typology"))

    low_rise = out["height_m"] <= float(albedo["low_rise_max_floors"]) * per_floor
    out["roof_albedo"] = np.where(low_rise, float(albedo["low_rise"]), float(albedo["other"]))
    out["roof_albedo_source"] = "typology_default"
    return out[
        [
            "id",
            "geometry",
            "height_m",
            "height_source",
            "building_tag",
            "footprint_m2",
            "roof_albedo",
            "roof_albedo_source",
        ]
    ]


def run(cfg: AreaConfig, paths: Paths) -> dict[str, int]:
    buildings = assign_heights(read_table(paths.table("osm_buildings")), cfg)
    write_table(buildings, paths.table("heights"))
    counts = {src: int((buildings["height_source"] == src).sum()) for src in HEIGHT_SOURCES}
    write_json({"by_height_source": counts, "buildings": len(buildings)}, paths.json("heights"))
    return counts
