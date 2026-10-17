"""Bundle writer and validator: the interface with the engine (pipeline/RULES.md, "Bundle tables")."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

from ..config import AreaConfig, Paths
from ..store import read_json, read_table, write_json, write_table
from .osm import bbox_polygon

BUNDLE_SCHEMA_VERSION = 1
ID_PREFIX = {
    "buildings": "b_",
    "blocks": "blk_",
    "chunks": "ch_",
    "wait_points": "wp_",
    "parcels": "pc_",
    "sites": "s_",
}

# Column -> kind: s string, f float, b bool, i int. A trailing "?" allows missing values.
SCHEMA: dict[str, dict[str, str]] = {
    "buildings": {
        "id": "s", "height_m": "f", "height_source": "s", "building_tag": "s", "footprint_m2": "f",
        "block_id": "s?", "roof_albedo": "f", "roof_albedo_source": "s",
    },
    "blocks": {
        "id": "s", "area_m2": "f", "coverage": "f", "built_form": "s", "I_s": "f", "G_c": "f", "G_buf": "f",
        "d_green": "f", "d_water": "f", "H_W": "f", "canyon_axis_deg": "f", "L_built": "f", "V": "f",
        "roof_albedo": "f", "wait_weight": "f", "split": "s", "building_count": "i",
        "median_footprint_m2": "f", "median_floors": "f", "i_s_source": "s", "g_c_source": "s",
        "g_buf_source": "s", "d_green_source": "s", "d_water_source": "s", "roof_albedo_source": "s",
        "h_w_source": "s", "canyon_axis_source": "s",
    },
    "chunks": {
        "id": "s", "run_id": "s", "block_id": "s?", "road_name": "s?", "road_class": "s", "road_width_m": "f",
        "width_source": "s", "bearing_deg": "f", "side": "s", "length_m": "f", "H_W": "f", "near_wait": "b",
        "footpath_source": "s",
    },
    "wait_points": {"id": "s", "kind": "s", "name": "s?", "weight": "f"},
    "parcels": {
        "id": "s", "block_id": "s", "area_m2": "f", "road_name": "s?", "road_width_m": "f",
        "street_bearing_deg": "f", "neighbour_height_m": "f", "vacant_tag": "b", "name": "s",
    },
    "sites": {
        "id": "s", "kind": "s", "name": "s", "quantity_min": "f", "quantity_max": "f", "rule": "s",
        "rejected": "b", "wait_point_id": "s?", "H_W": "f?", "block_id": "s?", "time_to_benefit": "s",
    },
}  # fmt: skip

CATEGORIES: dict[str, dict[str, set[str]]] = {
    "buildings": {"height_source": {"osm_height", "osm_levels", "open_buildings", "typology"}},
    "blocks": {"built_form": {"dense_low_rise", "other"}, "split": {"tune", "test"}},
    "chunks": {"footpath_source": {"osm", "derived"}, "side": {"left", "right"}},
    "wait_points": {"kind": {"school", "college", "hospital", "clinic", "marketplace", "bus_stop"}},
    "sites": {
        "kind": {"tree_row", "shade", "depave", "pocket_green", "cool_roof"},
        "time_to_benefit": {"weeks", "season", "years"},
    },
}

SOURCES_STATIC = [
    {
        "name": "OpenStreetMap (Overpass API)",
        "use": "buildings, roads, sidewalks, green, water, waiting points, public land",
        "licence": "ODbL 1.0",
        "url": "https://www.openstreetmap.org/copyright",
    },
    {
        "name": "Open-Meteo historical weather API (ERA5)",
        "use": "prevailing afternoon wind direction",
        "licence": "CC BY 4.0",
        "url": "https://open-meteo.com/en/docs/historical-weather-api",
    },
    {
        "name": "pvlib solar position",
        "use": "sun altitude and azimuth at the reference times (computed, clear sky)",
        "licence": "BSD-3-Clause",
        "url": "https://pvlib-python.readthedocs.io/",
    },
]


def git_sha() -> str:
    """Commit the bundle was built from; `ECOZONE_PIPELINE_SHA` overrides it (the committed fixture bundle)."""
    if override := os.environ.get("ECOZONE_PIPELINE_SHA"):
        return override
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=Path(__file__).parent
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True, cwd=Path(__file__).parent
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{sha}-dirty" if dirty else sha


# Geometry the API's contract can serve (contract/geo.py); a bundle with anything else fails here, not in the API.
GEOMETRY_TYPES: dict[str, set[str]] = {
    "blocks": {"Polygon"},
    "buildings": {"Polygon"},
    "chunks": {"LineString"},
    "wait_points": {"Point"},
    "parcels": {"Polygon"},
    "sites": {"LineString", "Polygon", "MultiPolygon"},
}


def validate_tables(tables: dict[str, gpd.GeoDataFrame], crs: str) -> list[str]:
    """Return every schema problem found; an empty list means the bundle is valid."""
    errors: list[str] = []
    for name, columns in SCHEMA.items():
        gdf = tables.get(name)
        if gdf is None:
            errors.append(f"{name}: table missing")
            continue
        if gdf.crs is None or gdf.crs.to_string() != crs:
            errors.append(f"{name}: CRS is {gdf.crs}, expected {crs}")
        for col, kind in columns.items():
            if col not in gdf.columns:
                errors.append(f"{name}.{col}: column missing")
                continue
            series = gdf[col]
            nullable = kind.endswith("?")
            if not nullable and series.isna().any():
                errors.append(f"{name}.{col}: {int(series.isna().sum())} missing values")
            present = series.dropna()
            ok = {
                "s": lambda s: all(isinstance(v, str) for v in s),
                "f": lambda s: pd.api.types.is_float_dtype(s) or pd.api.types.is_integer_dtype(s),
                "b": lambda s: pd.api.types.is_bool_dtype(s) or all(isinstance(v, bool) for v in s),
                "i": pd.api.types.is_integer_dtype,
            }[kind.rstrip("?")]
            if len(present) and not ok(present):
                errors.append(f"{name}.{col}: wrong type {series.dtype}, expected {kind.rstrip('?')}")
            if kind.rstrip("?") == "f" and present.map(lambda v: abs(v) == float("inf")).any():
                errors.append(f"{name}.{col}: infinite values")
        if "geometry" not in gdf.columns:
            errors.append(f"{name}: no geometry column")
            continue
        if not gdf.geometry.is_valid.all():
            errors.append(f"{name}: invalid geometries")
        if gdf.geometry.is_empty.any() or gdf.geometry.isna().any():
            errors.append(f"{name}: empty or missing geometries")
        wrong = sorted(set(gdf.geometry.geom_type.dropna()) - GEOMETRY_TYPES[name])
        if wrong:
            errors.append(
                f"{name}: geometry types {wrong} are not served by the API (allowed {sorted(GEOMETRY_TYPES[name])})"
            )
        if name == "sites" and "kind" in gdf.columns:
            rows = gdf[(gdf["kind"] == "tree_row") & (gdf.geometry.geom_type != "LineString")]
            if len(rows):
                errors.append(
                    f"sites: {len(rows)} tree rows are not a single LineString (ids {sorted(rows['id'])[:3]})"
                )
        if not gdf["id"].is_unique:
            errors.append(f"{name}: duplicate ids")
        prefix = ID_PREFIX[name]
        if not all(isinstance(v, str) and v.startswith(prefix) for v in gdf["id"]):
            errors.append(f"{name}: ids must start with {prefix!r}")
        for col, allowed in CATEGORIES.get(name, {}).items():
            if col in gdf.columns and not set(gdf[col].dropna()) <= allowed:
                errors.append(f"{name}.{col}: unexpected values {sorted(set(gdf[col].dropna()) - allowed)}")

    block_ids = set(tables["blocks"]["id"]) if "blocks" in tables else set()
    for name in ("buildings", "chunks", "parcels", "sites"):
        gdf = tables.get(name)
        if gdf is not None and "block_id" in gdf.columns:
            stray = set(gdf["block_id"].dropna()) - block_ids
            if stray:
                errors.append(f"{name}.block_id: unknown blocks {sorted(stray)[:3]}")
    if "sites" in tables and "wait_points" in tables:
        stray = set(tables["sites"]["wait_point_id"].dropna()) - set(tables["wait_points"]["id"])
        if stray:
            errors.append(f"sites.wait_point_id: unknown waiting points {sorted(stray)[:3]}")
    return errors


def build_meta(cfg: AreaConfig, paths: Paths, tables: dict[str, gpd.GeoDataFrame]) -> dict[str, Any]:
    sun_wind = read_json(paths.json("sun_wind"))
    attrs = read_json(paths.json("attributes"))
    osm = read_json(paths.json("osm"))
    geo = read_json(paths.json("geometry"))
    heights = read_json(paths.json("heights"))
    area = cfg["area"]
    ref = cfg["reference"]
    box = bbox_polygon(cfg).bounds
    gaps = {
        "buildings_height_from_typology": heights["by_height_source"]["typology"],
        "buildings_total": heights["buildings"],
        "footpath_chunks_derived_from_road_edge": geo["chunks_derived_footpath"],
        "chunks_width_from_road_class": geo["chunks_width_from_road_class"],
        "chunks_total": geo["chunks"],
        "chunks_without_block": geo["chunks_without_block"],
        "roof_albedo_default_buildings": int((tables["buildings"]["roof_albedo_source"] != "earth_engine").sum()),
        "vegetation_and_impervious_from_osm_proxy": len(tables["blocks"]),
        "canyon_axis_from_block_shape": attrs["canyon_axis_from_block_shape"],
    }
    sources = [dict(s) for s in SOURCES_STATIC]
    fetch = osm.get("fetch", {})
    sources[0].update(
        fetched_at=fetch.get("fetched_at"),
        snapshot=fetch.get("osm_base_timestamp"),
        query_sha256=fetch.get("query_sha256"),
    )
    sources[1].update(
        fetched_at=sun_wind["wind_provenance"].get("fetched_at"),
        period=f"{cfg['wind']['start_date']} to {cfg['wind']['end_date']}",
    )
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "area_id": cfg.area_id,
        "name": area["name"],
        "city": area["city"],
        "bundle_version": f"v{cfg.bundle_version}",
        "crs": cfg.crs,
        "bbox_wgs84": list(cfg.bbox_wgs84),
        "bbox_xy": [round(v, 2) for v in box],
        "reference_date": str(ref["date"]),
        "shade_times": list(ref["times_ist"]),
        "timezone": ref["timezone"],
        "sun": sun_wind["sun"],
        "wind_from_deg": sun_wind["wind_from_deg"],
        "wind_provenance": sun_wind["wind_provenance"],
        "V_ref": attrs["v_ref"],
        "metres_per_floor": float(cfg["osm"]["metres_per_floor"]),
        "counts": {
            "blocks": len(tables["blocks"]),
            "buildings": len(tables["buildings"]),
            "segments": len(tables["chunks"]),
            "wait_points": len(tables["wait_points"]),
            "sites": len(tables["sites"]),
            "parcels": len(tables["parcels"]),
        },
        "buildings_by_height_source": heights["by_height_source"],
        "derived_footpath_chunks": geo["chunks_derived_footpath"],
        "data_gaps": gaps,
        "skipped_steps": ["earth_engine"],
        "attribution": cfg["osm"]["attribution"],
        "sources": sources,
        "settings_hash": cfg.settings_hash,
        "pipeline_git_sha": git_sha(),
    }


def collect_tables(paths: Paths) -> dict[str, gpd.GeoDataFrame]:
    buildings = read_table(paths.table("buildings_class"))
    return {
        "buildings": buildings,
        "blocks": read_table(paths.table("blocks")),
        "chunks": read_table(paths.table("chunks")),
        "wait_points": read_table(paths.table("osm_wait_points")),
        "parcels": read_table(paths.table("parcels")),
        "sites": read_table(paths.table("sites")),
    }


def run(cfg: AreaConfig, paths: Paths, *, out_dir: Path | None = None) -> Path:
    tables = collect_tables(paths)
    errors = validate_tables(tables, cfg.crs)
    if errors:
        raise ValueError("bundle failed validation:\n  " + "\n  ".join(errors))
    target = out_dir or paths.bundle(cfg.bundle_version)
    if target.exists():
        shutil.rmtree(target)
    for name, gdf in tables.items():
        write_table(gdf, target / f"{name}.parquet")
    write_json(build_meta(cfg, paths, tables), target / "meta.json")
    return target


def load_tables(bundle_dir: Path) -> dict[str, gpd.GeoDataFrame]:
    return {name: read_table(bundle_dir / f"{name}.parquet") for name in SCHEMA}
