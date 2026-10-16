"""Helpers for the tiny synthetic area; imported by the tests (pipeline/tests is on pytest's pythonpath)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd

from ecozone_pipeline.config import AreaConfig, Paths
from ecozone_pipeline.steps import attributes, bundle, classify, geometry, heights, osm, sun_wind

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class Tiny:
    cfg: AreaConfig
    paths: Paths
    bundle_dir: Path

    def table(self, name: str) -> gpd.GeoDataFrame:
        return gpd.read_parquet(self.paths.table(name))

    def bundle_table(self, name: str) -> gpd.GeoDataFrame:
        return gpd.read_parquet(self.bundle_dir / f"{name}.parquet")


def run_all(cfg: AreaConfig, paths: Paths, out: Path) -> Path:
    osm.run(cfg, paths)
    sun_wind.run(cfg, paths)
    heights.run(cfg, paths)
    geometry.run(cfg, paths)
    classify.run(cfg, paths)
    attributes.run(cfg, paths)
    return bundle.run(cfg, paths, out_dir=out)
