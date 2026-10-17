from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import LineString
from tiny_area import Tiny

from ecozone_pipeline.steps.classify import SITE_KINDS, TIME_TO_BENEFIT, tree_row_sites


def test_every_intervention_type_has_sites(tiny: Tiny) -> None:
    sites = tiny.table("sites")
    assert set(sites["kind"]) == set(SITE_KINDS)


def test_tree_rows_follow_the_canopy_rule(tiny: Tiny) -> None:
    trees = tiny.table("sites").query("kind == 'tree_row'")
    limit = float(tiny.cfg["sites"]["tree_row"]["canopy_hw_limit"])
    rejected, accepted = trees[trees["rejected"]], trees[~trees["rejected"]]
    assert len(rejected) > 0
    assert len(accepted) > 0
    assert (rejected["H_W"] >= limit).all()
    assert (rejected["rule"] == "CANOPY_OBSTRUCTION").all()
    assert (accepted["H_W"] < limit).all()
    assert (accepted["rule"] == "tree_row_strip").all()


def test_only_tree_rows_are_ever_rejected(tiny: Tiny) -> None:
    sites = tiny.table("sites")
    assert set(sites.loc[sites["rejected"], "kind"]) == {"tree_row"}


def test_quantity_ranges_are_ordered_and_positive(tiny: Tiny) -> None:
    sites = tiny.table("sites")
    assert (sites["quantity_min"] > 0).all()
    assert (sites["quantity_min"] <= sites["quantity_max"]).all()


def test_shade_site_sits_on_a_footpath_beside_a_waiting_point(tiny: Tiny) -> None:
    shade = tiny.table("sites").query("kind == 'shade'")
    wait = tiny.table("osm_wait_points").set_index("id")
    near = float(tiny.cfg["wait_points"]["near_wait_m"])
    assert shade["wait_point_id"].notna().all()
    for site in shade.itertuples():
        assert site.geometry.distance(wait.loc[site.wait_point_id, "geometry"]) <= near


def test_depave_sites_exclude_buildings(tiny: Tiny) -> None:
    depave = tiny.table("sites").query("kind == 'depave'")
    buildings = tiny.table("heights").geometry.union_all()
    assert len(depave) == 2
    assert all(g.intersection(buildings.buffer(0.9)).area < 1e-6 for g in depave.geometry)


def test_cool_roofs_only_in_dense_low_rise_blocks(tiny: Tiny) -> None:
    roofs = tiny.table("sites").query("kind == 'cool_roof'")
    blocks = tiny.table("blocks_class").set_index("id")
    assert len(roofs) == 1
    assert (blocks.loc[roofs["block_id"], "built_form"] == "dense_low_rise").all()
    assert roofs.geometry.iloc[0].geom_type == "MultiPolygon"


def test_time_to_benefit_follows_the_intervention_library(tiny: Tiny) -> None:
    sites = tiny.table("sites")
    assert (sites["time_to_benefit"] == sites["kind"].map(TIME_TO_BENEFIT)).all()
    assert TIME_TO_BENEFIT["shade"] == "weeks"
    assert TIME_TO_BENEFIT["tree_row"] == "years"


def test_built_form(tiny: Tiny) -> None:
    blocks = tiny.table("blocks_class")
    dense = blocks[blocks["built_form"] == "dense_low_rise"]
    assert len(dense) == 1
    assert dense["coverage"].iloc[0] >= float(tiny.cfg["dense_low_rise"]["min_coverage"])
    assert set(blocks["built_form"]) <= {"dense_low_rise", "other"}


def test_parcels_are_open_land_fronting_a_road(tiny: Tiny) -> None:
    parcels = tiny.table("parcels")
    c = tiny.cfg["classify"]
    assert len(parcels) == 3
    assert parcels["area_m2"].between(c["min_parcel_m2"], c["max_parcel_m2"]).all()
    assert (parcels["street_bearing_deg"].between(0, 180, inclusive="left")).all()
    assert parcels["vacant_tag"].sum() == 1
    buildings = tiny.table("heights").geometry.union_all()
    assert not parcels.geometry.intersects(buildings.buffer(-0.1)).any()
    assert parcels["id"].tolist() == ["pc_001", "pc_002", "pc_003"]


def test_parcel_count_is_capped(tiny: Tiny) -> None:
    assert len(tiny.table("parcels")) <= int(tiny.cfg["classify"]["max_parcels"])


@pytest.mark.parametrize("kind", SITE_KINDS)
def test_site_geometry_is_not_empty(tiny: Tiny, kind: str) -> None:
    sites = tiny.table("sites").query("kind == @kind")
    assert (~sites.geometry.is_empty).all()


def _run(hw: list[float], gap_after: int | None = None) -> gpd.GeoDataFrame:
    """One east-west footpath run of 10 m chunks with the given H/W per chunk; optionally a 5 m gap after one."""
    rows = []
    x = 0.0
    for i, value in enumerate(hw):
        rows.append(
            {
                "id": f"ch_{i}",
                "run_id": "run_1",
                "road_name": "Test Road",
                "side": "north",
                "road_width_m": 12.0,
                "length_m": 10.0,
                "H_W": value,
                "block_id": "blk_1",
                "geometry": LineString([(x, 0), (x + 10, 0)]),
            }
        )
        x += 10.0 + (5.0 if gap_after == i else 0.0)
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:32643")


def test_one_deep_stretch_rejects_the_whole_tree_row(tiny: Tiny) -> None:
    """H/W averages 0.78 here, but the 1.4 stretch is a deep street: the site rule (PLANNING.md Oct 15) applies."""
    (row,) = tree_row_sites(_run([0.4, 0.5, 1.4, 0.8]), tiny.cfg)
    assert row["rejected"] is True
    assert row["rule"] == "CANOPY_OBSTRUCTION"
    assert row["H_W"] == pytest.approx(1.4)


def test_a_shallow_run_is_accepted(tiny: Tiny) -> None:
    (row,) = tree_row_sites(_run([0.4, 0.5, 0.9, 0.8]), tiny.cfg)
    assert row["rejected"] is False
    assert row["H_W"] == pytest.approx(0.9)


def test_a_gap_in_a_run_splits_it_into_single_linestrings(tiny: Tiny) -> None:
    rows = tree_row_sites(_run([0.4] * 8, gap_after=3), tiny.cfg)
    assert len(rows) == 2
    assert all(r["geometry"].geom_type == "LineString" for r in rows)
