"""Waiting points covered: a shade structure at the point, or footpath within the radius newly shaded at 3 pm."""

from __future__ import annotations

from pathlib import Path

import pytest

import ecozone_engine as engine
from ecozone_engine.model import Change, UnitCost, UnitCosts

TINY = Path(__file__).parent / "fixtures" / "tiny"

COSTS: UnitCosts = {
    "tree_row": UnitCost(unit="tree", inr=5_000.0, source="test"),
    "shade": UnitCost(unit="m2", inr=2_000.0, source="test"),
    "depave": UnitCost(unit="m2", inr=500.0, source="test"),
    "pocket_green": UnitCost(unit="m2", inr=300.0, source="test"),
    "cool_roof": UnitCost(unit="m2", inr=200.0, source="test"),
}


@pytest.fixture(scope="module")
def area() -> engine.AreaModel:
    return engine.load_bundle(TINY)


def covered(area: engine.AreaModel, *site_ids: str) -> int:
    sites = {s.site_id: s for s in area.sites}
    changes = [Change(kind=sites[i].kind, site_id=i, quantity=sites[i].quantity_min) for i in site_ids]  # type: ignore[arg-type]
    return engine.rescore(area, changes, COSTS).wait_points_covered


def test_no_changes_cover_nothing(area: engine.AreaModel) -> None:
    assert covered(area) == 0


def test_a_shade_structure_covers_its_waiting_point(area: engine.AreaModel) -> None:
    assert covered(area, "s_0021") == 1


def test_a_tree_row_covers_a_waiting_point_when_footpath_near_it_gains_shade(area: engine.AreaModel) -> None:
    site = next(s for s in area.sites if s.site_id == "s_0013")
    assert site.kind == "tree_row" and site.wait_point_id is None  # the old rule counted only shade structures
    assert covered(area, "s_0013") == 1


def test_a_tree_row_away_from_waiting_points_covers_none(area: engine.AreaModel) -> None:
    assert covered(area, "s_0004") == 0


def test_interventions_that_do_not_shade_footpath_cover_none(area: engine.AreaModel) -> None:
    assert covered(area, "s_0023", "s_0025", "s_0026") == 0


def test_the_count_is_a_union_of_distinct_waiting_points(area: engine.AreaModel) -> None:
    assert covered(area, "s_0021", "s_0022") == 2
    assert max(covered(area, "s_0013"), covered(area, "s_0021")) <= covered(area, "s_0013", "s_0021") <= 2


def test_the_count_ignores_change_order(area: engine.AreaModel) -> None:
    assert covered(area, "s_0013", "s_0021", "s_0014") == covered(area, "s_0014", "s_0013", "s_0021")
