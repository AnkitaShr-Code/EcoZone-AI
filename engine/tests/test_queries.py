"""summary(), layer() and hotspots() through the public API on the tiny fixture.

The property keys asserted here are the contract between the engine and api/to_contract.py
(engine/RULES.md, "Layer properties").
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from shapely.geometry import LineString, Point

import ecozone_engine as engine
from ecozone_engine.shade import compute_chunk_shading

TINY = Path(__file__).parent / "fixtures" / "tiny"
META = json.loads((TINY / "meta.json").read_text())

LAYERS: tuple[engine.LayerName, ...] = ("blocks", "segments", "buildings", "wait_points", "parcels", "sites")
KEYS: dict[str, set[str]] = {
    "blocks": {"area_m2", "scores", "priority", "priority_class", "built_form", "wait_weight", "drivers"},
    "segments": {"road_name", "road_class", "length_m", "block_id", "near_wait", "shaded"},
    "buildings": {"height_m", "height_source"},
    "wait_points": {"kind", "name", "weight"},
    "parcels": {
        "block_id",
        "name",
        "area_m2",
        "road_name",
        "road_width_m",
        "street_bearing_deg",
        "neighbour_height_m",
    },
    "sites": {"kind", "name", "quantity", "time_to_benefit", "wait_point_id", "h_w", "rejected"},
}
DRIVER_TAGS = {"SHADE_GAIN", "IMPERVIOUS_LOSS", "ALBEDO_GAIN", "GREEN_LINK", "WAIT_POINT_COVERED"}


@pytest.fixture(scope="module")
def area() -> engine.AreaModel:
    return engine.load_bundle(TINY)


def _numbers(value: object) -> list[float]:
    """Every float inside a property value, however nested."""
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, engine.Scores):
        return [value.vci, value.hei, value.gcs, value.pss]
    if isinstance(value, (tuple, list)):
        return [n for v in value for n in _numbers(v)]  # pyright: ignore[reportUnknownVariableType]
    return []


# ── summary ───────────────────────────────────────────────────────────────────


def test_summary_carries_the_bundle_meta(area: engine.AreaModel) -> None:
    s = engine.summary(area)
    assert (s.area_id, s.name, s.city, s.bundle_version) == ("tiny", META["name"], "Test", "v1")
    assert s.bbox_xy == tuple(META["bbox_xy"])
    assert s.reference_date == "2026-04-15"
    assert s.shade_times == ("13:00", "15:00", "16:00")
    assert s.wind_from_deg == 300.0
    assert s.metres_per_floor == 3.0
    assert s.derived_footpath_chunks == META["derived_footpath_chunks"]
    assert s.skipped_steps == ("earth_engine", "baselines")
    assert s.attribution == META["attribution"]
    assert s.baseline == area.area_baseline


def test_summary_counts_match_the_layers(area: engine.AreaModel) -> None:
    s = engine.summary(area)
    assert s.counts == {
        "blocks": 6,
        "buildings": 24,
        "segments": 123,
        "wait_points": 3,
        "sites": sum(1 for f in engine.layer(area, "sites") if not f.properties["rejected"]),
        "parcels": 3,
    }
    assert s.counts["sites"] < len(area.sites)  # rejected tree rows are not counted
    assert dict(s.buildings_by_height_source) == META["buildings_by_height_source"]


# ── layers ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", LAYERS)
def test_layer_property_keys_ids_and_order(area: engine.AreaModel, name: engine.LayerName) -> None:
    features = engine.layer(area, name)
    assert features
    ids = [f.id for f in features]
    assert ids == sorted(set(ids)), "ids must be unique and in sorted order"
    for f in features:
        assert not f.geometry.is_empty
        expected = KEYS[name] | ({"points"} if name == "sites" and f.properties["kind"] == "tree_row" else set())
        assert set(f.properties) == expected
        assert all(math.isfinite(n) for v in f.properties.values() for n in _numbers(v))


@pytest.mark.parametrize("name", LAYERS)
def test_layer_is_deterministic(area: engine.AreaModel, name: engine.LayerName) -> None:
    again = engine.load_bundle(TINY)
    assert repr(engine.layer(area, name)) == repr(engine.layer(again, name))


def test_layer_counts_match_the_tables(area: engine.AreaModel) -> None:
    assert len(engine.layer(area, "blocks")) == len(area.blocks)
    assert len(engine.layer(area, "segments")) == len(area.chunks) == 123
    assert len(engine.layer(area, "buildings")) == len(area.buildings)
    assert len(engine.layer(area, "wait_points")) == len(area.wait_points)
    assert len(engine.layer(area, "parcels")) == len(area.parcels)


def test_blocks_carry_baseline_scores_priority_and_drivers(area: engine.AreaModel) -> None:
    baselines = dict(area.block_baselines)
    features = engine.layer(area, "blocks")
    for f in features:
        p = f.properties
        assert p["scores"] == baselines[f.id]
        assert p["priority_class"] in {"high", "medium", "low"}
        assert p["built_form"] in {"dense_low_rise", "other"}
        assert set(p["drivers"]) <= DRIVER_TAGS  # pyright: ignore[reportArgumentType]
    assert {f.properties["priority_class"] for f in features} == {"high", "medium", "low"}
    # blk_0001 sits next to the hospital and a bus stop and has almost no shade
    first = features[0].properties
    assert first["wait_weight"] == 7.0
    assert {"SHADE_GAIN", "WAIT_POINT_COVERED", "GREEN_LINK"} <= set(first["drivers"])  # pyright: ignore[reportArgumentType]


def test_segments_carry_baseline_shade_and_road_attributes(area: engine.AreaModel) -> None:
    shading = compute_chunk_shading(area)
    features = engine.layer(area, "segments")
    assert all(isinstance(f.geometry, LineString) for f in features)
    assert {f.id: f.properties["shaded"] for f in features} == shading
    assert any(any(f.properties["shaded"]) for f in features)  # pyright: ignore[reportArgumentType]
    assert {f.properties["road_name"] for f in features} >= {"Road One"}
    assert all(isinstance(f.properties["road_class"], str) and f.properties["road_class"] for f in features)
    assert all(f.properties["block_id"] in {b.block_id for b in area.blocks} for f in features)


def test_buildings_wait_points_and_parcels_carry_their_bundle_columns(area: engine.AreaModel) -> None:
    buildings = engine.layer(area, "buildings")
    assert {f.properties["height_source"] for f in buildings} == {"osm_height", "osm_levels", "typology"}
    assert next(f for f in buildings if f.id == "b_w10").properties["height_m"] == 9.0

    kinds = {f.id: f.properties["kind"] for f in engine.layer(area, "wait_points")}
    assert kinds["wp_w19"] == "hospital"
    assert next(f for f in engine.layer(area, "wait_points") if f.id == "wp_w19").properties["name"] == "Test Hospital"

    parcels = {f.id: f.properties for f in engine.layer(area, "parcels")}
    assert parcels["pc_001"]["name"] == "Open plot on an unnamed lane"
    assert parcels["pc_001"]["road_name"] is None
    assert parcels["pc_001"]["neighbour_height_m"] == 15.0


def test_sites_list_rejected_rows_flagged_and_keep_quantity_in_range(area: engine.AreaModel) -> None:
    rejected = {s.site_id for s in area.sites if s.rejected}
    assert rejected, "the fixture must contain rejected tree rows"
    sites = engine.layer(area, "sites")
    assert len(sites) == len(area.sites)  # every site is listed, rejected ones flagged
    assert {f.id for f in sites if f.properties["rejected"]} == rejected
    offered = [f for f in sites if not f.properties["rejected"]]
    by_id = {s.site_id: s for s in area.sites}
    for f in offered:
        site = by_id[f.id]
        assert f.properties["kind"] == site.kind
        assert site.quantity_min <= f.properties["quantity"] <= site.quantity_max  # pyright: ignore[reportOperatorIssue]
        assert f.properties["name"]
    assert {"tree_row", "shade"} <= {f.properties["kind"] for f in offered}


def test_tree_rows_list_the_tree_positions_rescore_shades_with(area: engine.AreaModel) -> None:
    rows = [f for f in engine.layer(area, "sites") if f.properties["kind"] == "tree_row"]
    assert rows
    for f in rows:
        points: tuple[tuple[float, float], ...] = f.properties["points"]  # pyright: ignore[reportAssignmentType]
        assert len(points) == round(f.properties["quantity"])  # pyright: ignore[reportArgumentType]
        assert all(f.geometry.distance(Point(xy)) < 1e-6 for xy in points)
        assert f.properties["h_w"] is not None
        if f.properties["rejected"]:
            assert f.properties["h_w"] >= 1.0  # type: ignore[operator]
        else:
            assert f.properties["h_w"] < 1.0  # type: ignore[operator]  # the canopy rule keeps deep streets out
    assert all("points" not in f.properties for f in engine.layer(area, "sites") if f.properties["kind"] != "tree_row")


def test_every_offered_site_scores_as_a_single_site(area: engine.AreaModel) -> None:
    costs: engine.UnitCosts = {
        k: engine.UnitCost(unit="u", inr=1000.0, source="test")
        for k in ("tree_row", "shade", "depave", "pocket_green", "cool_roof")
    }
    for f in engine.layer(area, "sites"):
        result = engine.single_site(area, f.id, costs)
        assert result.site_id == f.id
        assert math.isfinite(result.acs_gain)


# ── hotspots ──────────────────────────────────────────────────────────────────


def test_hotspots_are_ranked_with_drivers_that_match_the_blocks_layer(area: engine.AreaModel) -> None:
    blocks = {f.id: f.properties for f in engine.layer(area, "blocks")}
    spots = engine.hotspots(area, 10)
    assert [h.rank for h in spots] == list(range(1, len(blocks) + 1))
    assert [h.priority for h in spots] == sorted((h.priority for h in spots), reverse=True)
    for h in spots:
        assert h.drivers == blocks[h.block_id]["drivers"]
        assert h.priority == blocks[h.block_id]["priority"]
        assert h.priority_class == blocks[h.block_id]["priority_class"]
        assert h.scores == blocks[h.block_id]["scores"]
    assert any(h.drivers for h in spots)
    assert len(engine.hotspots(area, 2)) == 2


def test_a_rejected_site_gets_a_reason_but_no_score_and_rescore_still_refuses_it(area: engine.AreaModel) -> None:
    from ecozone_engine.errors import InvalidChangeError
    from ecozone_engine.model import Change, UnitCost, UnitCosts

    costs: UnitCosts = {
        "tree_row": UnitCost(unit="tree", inr=5_000.0, source="test"),
        "shade": UnitCost(unit="m2", inr=2_000.0, source="test"),
        "depave": UnitCost(unit="m2", inr=500.0, source="test"),
        "pocket_green": UnitCost(unit="m2", inr=300.0, source="test"),
        "cool_roof": UnitCost(unit="m2", inr=200.0, source="test"),
    }
    site = next(s for s in area.sites if s.rejected)
    single = engine.single_site(area, site.site_id, costs)
    assert single.ventilation_ok is False
    assert single.acs_gain == 0.0 and single.drivers == ()
    assert single.ventilation_reason and "breeze" in single.ventilation_reason
    assert single.cost_inr > 0
    with pytest.raises(InvalidChangeError):
        engine.rescore(area, [Change(kind="tree_row", site_id=site.site_id, quantity=site.quantity_min)], costs)
