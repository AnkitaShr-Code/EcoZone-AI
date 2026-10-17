from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from shapely import Point, box
from tiny_area import Tiny

from ecozone_engine.model import WaitPointRow
from ecozone_engine.priority import wait_weight_sum
from ecozone_pipeline.steps.attributes import axis_mean_deg, longest_built_run, share, split_for
from ecozone_pipeline.steps.sun_wind import prevailing_wind_from_deg, sun_table

_DECCAN_BUNDLE = Path(__file__).parents[3] / "EcoZone-AI" / "data" / "areas" / "deccan" / "v1"


def angle_gap(a: float, b: float, period: float = 360.0) -> float:
    return abs((a - b + period / 2) % period - period / 2)


def test_sun_table_for_pune_in_april(tiny: Tiny) -> None:
    sun = sun_table(tiny.cfg)
    assert [s["time"] for s in sun] == ["13:00", "15:00", "16:00"]
    alt = [s["altitude_deg"] for s in sun]
    assert alt == sorted(alt, reverse=True)
    assert 77 < alt[0] < 81  # near-overhead at 13:00 in mid April at 18.5 N
    assert 52 < alt[1] < 56
    assert 38 < alt[2] < 42
    az = [s["azimuth_deg"] for s in sun]
    assert all(180 < a < 290 for a in az), "afternoon sun is in the west-south-west"


def test_prevailing_wind_vector_mean() -> None:
    assert angle_gap(prevailing_wind_from_deg(np.array([350.0, 10.0]), np.array([2.0, 2.0])), 0) < 1e-6
    assert prevailing_wind_from_deg(np.array([270.0]), np.array([5.0])) == pytest.approx(270)
    assert prevailing_wind_from_deg(np.array([90.0, 270.0, 270.0]), np.array([1.0, 1.0, 3.0])) == pytest.approx(270)


def test_wind_override_skips_the_download(tiny: Tiny) -> None:
    assert tiny.paths.json("sun_wind").exists()
    assert not (tiny.paths.raw / "open_meteo_wind.json").exists()


def test_axis_mean_treats_a_bearing_and_its_reverse_as_one_axis() -> None:
    assert axis_mean_deg(np.array([90.0, 270.0]), np.array([10.0, 10.0])) == pytest.approx(90)
    assert angle_gap(axis_mean_deg(np.array([10.0, 170.0]), np.array([5.0, 5.0])), 0, 180) < 1e-6


def test_split_is_stable_and_balanced() -> None:
    ids = [f"blk_{i:04d}" for i in range(400)]
    halves = [split_for(i, "seed") for i in ids]
    assert halves == [split_for(i, "seed") for i in ids]
    assert 0.4 < halves.count("tune") / len(halves) < 0.6
    assert split_for("blk_0001", "a") in {"tune", "test"}


def test_share_is_a_percentage() -> None:
    assert share(box(0, 0, 5, 10), box(0, 0, 10, 10)) == 50.0
    assert share(box(20, 20, 30, 30), box(0, 0, 10, 10)) == 0.0


def test_longest_built_run_along_the_wind_line() -> None:
    wall = box(-20, -3, 20, 3).union(box(100, -3, 110, 3))
    west_wind = 270.0  # blows from the west: the line runs east-west through the centre
    assert longest_built_run(Point(0, 0), west_wind, 300, wall) == pytest.approx(40)
    assert longest_built_run(Point(0, 200), west_wind, 300, wall) == 0


def test_block_attributes_are_in_range(tiny: Tiny) -> None:
    b = tiny.bundle_table("blocks")
    for col in ("I_s", "G_c", "G_buf"):
        assert b[col].between(0, 100).all(), col
    assert b["d_water"].between(0, tiny.cfg["attributes"]["d_water_cap_m"]).all()
    assert b["d_green"].between(0, tiny.cfg["attributes"]["d_green_cap_m"]).all()
    assert b["canyon_axis_deg"].between(0, 180).all()
    assert b["roof_albedo"].between(0, 1).all()
    assert (b["V"] >= 0).all()
    assert (b["L_built"] >= 0).all()
    assert b["wait_weight"].min() >= 0


def test_block_attributes_reflect_the_layout(tiny: Tiny) -> None:
    b = tiny.bundle_table("blocks").set_index("id")
    dense = b[b["built_form"] == "dense_low_rise"].iloc[0]
    park_block = b.loc[b["G_c"].idxmax()]
    assert park_block["G_c"] > dense["G_c"]
    assert park_block["d_green"] == 0
    assert b["wait_weight"].max() >= 3  # the school and hospital waiting points


def test_v_ref_is_the_95th_percentile_of_block_volume(tiny: Tiny) -> None:
    b = tiny.bundle_table("blocks")
    expected = float(np.percentile(b.loc[b["V"] > 0, "V"], 95))
    assert tiny.cfg["attributes"]["v_ref_percentile"] == 95
    assert json.loads((tiny.bundle_dir / "meta.json").read_text())["V_ref"] == pytest.approx(expected)


def test_wait_weight_column_equals_engine_value(tiny: Tiny) -> None:
    """Bundle wait_weight column must equal engine's wait_weight_sum() on every block.

    This guards against pipeline/engine divergence after the single-computation rule.
    """
    blocks = tiny.bundle_table("blocks")
    wp_gdf = tiny.bundle_table("wait_points")
    wp_rows: list[WaitPointRow] = [
        WaitPointRow(wait_id=str(row.id), geometry=row.geometry, kind=str(row.kind), weight=float(row.weight))
        for row in wp_gdf.itertuples(index=False)
    ]
    for row in blocks.itertuples(index=False):
        expected = wait_weight_sum(row.geometry, wp_rows)
        assert float(row.wait_weight) == pytest.approx(expected, abs=1e-9), (
            f"block {row.id}: bundle wait_weight={row.wait_weight:.4f} != engine {expected:.4f}"
        )


@pytest.mark.skipif(
    not _DECCAN_BUNDLE.exists(),
    reason=f"Deccan bundle not present at {_DECCAN_BUNDLE}",
)
def test_wait_weight_column_equals_engine_value_deccan() -> None:
    """Same guard as the tiny-fixture test, run on the real Deccan bundle.

    Skipped when data/areas/deccan/v1 is not present (e.g. CI without the bundle).
    """
    blocks = gpd.read_parquet(_DECCAN_BUNDLE / "blocks.parquet")
    wp_gdf = gpd.read_parquet(_DECCAN_BUNDLE / "wait_points.parquet")
    wp_rows: list[WaitPointRow] = [
        WaitPointRow(wait_id=str(row.id), geometry=row.geometry, kind=str(row.kind), weight=float(row.weight))
        for row in wp_gdf.itertuples(index=False)
    ]
    for row in blocks.itertuples(index=False):
        expected = wait_weight_sum(row.geometry, wp_rows)
        assert float(row.wait_weight) == pytest.approx(expected, abs=1e-9), (
            f"deccan block {row.id}: bundle wait_weight={row.wait_weight:.4f} != engine {expected:.4f}"
        )
