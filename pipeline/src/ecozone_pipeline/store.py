"""GeoParquet and JSON helpers shared by the steps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import geopandas as gpd
import shapely
from shapely.geometry.base import BaseGeometry


def write_table(gdf: gpd.GeoDataFrame, path: Path) -> None:
    """Write a GeoParquet file with valid, non-empty geometry only (pipeline/RULES.md, geometry hygiene)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf = clean_geometry(gdf)
    gdf.to_parquet(path, index=False)


def read_table(path: Path) -> gpd.GeoDataFrame:
    return gpd.read_parquet(path)


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def clean_geometry(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Make every geometry valid and drop empties."""
    if gdf.empty:
        return gdf
    fixed = gdf.copy()
    fixed["geometry"] = fixed.geometry.make_valid()
    keep = ~(fixed.geometry.isna() | fixed.geometry.is_empty)
    return cast(gpd.GeoDataFrame, fixed.loc[keep].reset_index(drop=True))


def text(value: object) -> str | None:
    """A non-empty string, or None for missing values (parquet round-trips None as NaN)."""
    return value if isinstance(value, str) and value else None


def polygonal(geom: BaseGeometry) -> BaseGeometry:
    """Keep only the polygon parts of a geometry (make_valid can return collections)."""
    if geom.is_empty or geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    parts = [g for g in getattr(geom, "geoms", []) if g.geom_type in ("Polygon", "MultiPolygon")]
    return shapely.union_all(parts) if parts else shapely.Polygon()
