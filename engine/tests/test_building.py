"""apply_building: adding a building never improves ventilation (PLANNING.md "Terms and what changes them").

Fixture: engine/tests/fixtures/tiny. pc_001 is on blk_0003 (H/W 1.5591, canyon axis 90.3685, L_built 16.1079) with a
12 m road; the wind comes from 300 degrees, so it blows along 120 degrees.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest

import ecozone_engine as engine
from ecozone_engine.building import apply_building
from ecozone_engine.model import Change, UnitCost, UnitCosts
from ecozone_engine.settings import SETTINGS

TINY = Path(__file__).parent / "fixtures" / "tiny"
COSTS: UnitCosts = {"shade": UnitCost(unit="m2", inr=2_000.0, source="test")}
PARCELS = {"pc_001": "blk_0003", "pc_002": "blk_0002", "pc_003": "blk_0004"}
ORIENTATIONS = [float(d) for d in range(0, 180, 15)]
EPS = 1e-9


@pytest.fixture(scope="module")
def area() -> engine.AreaModel:
    return engine.load_bundle(TINY)


def building(parcel_id: str, floors: float, orientation_deg: float, footprint_pct: float = 80.0) -> Change:
    return Change(
        kind="building",
        site_id=parcel_id,
        quantity=1.0,
        params=(
            ("floors", floors),
            ("footprint_pct", footprint_pct),
            ("green_pct", 5.0),
            ("orientation_deg", orientation_deg),
        ),
    )


def block_vci_change(area: engine.AreaModel, parcel_id: str, floors: float, orientation_deg: float) -> float:
    """After minus before VCI on the parcel's block."""
    r = engine.rescore(area, [building(parcel_id, floors, orientation_deg)], COSTS)
    blk = next(b for b in r.blocks if b.block_id == PARCELS[parcel_id])
    return blk.after.vci - blk.before.vci


# ── golden deltas ─────────────────────────────────────────────────────────────


def test_low_rise_leaves_the_block_hw_alone(area: engine.AreaModel) -> None:
    """1 floor on a 12 m road: H/W = 3 / 12 = 0.25, below the block's 1.5591, so the block keeps its H/W
    (the old code lowered it by 1.3091)."""
    deltas = apply_building(area, building("pc_001", 1.0, 120.0))["blk_0003"]
    assert deltas["H_W"] == 0.0


def test_tall_building_raises_the_block_hw_to_its_own(area: engine.AreaModel) -> None:
    """12 floors on a 12 m road: H/W = 36 / 12 = 3.0; the block rises from 1.5591 to 3.0."""
    blk = next(b for b in area.blocks if b.block_id == "blk_0003")
    deltas = apply_building(area, building("pc_001", 12.0, 120.0))["blk_0003"]
    assert deltas["H_W"] == pytest.approx(3.0 - blk.H_W)


def test_orientation_along_the_wind_does_not_move_the_axis(area: engine.AreaModel) -> None:
    """Wind blows along 120 degrees. The block's axis (90.3685) is 29.63 degrees off it; a building turned to
    120 degrees is 0 degrees off, so it cannot improve the block and the axis is kept."""
    assert apply_building(area, building("pc_001", 6.0, 120.0))["blk_0003"]["canyon_axis_deg"] == 0.0


def test_orientation_across_the_wind_sets_the_axis(area: engine.AreaModel) -> None:
    """A building turned to 30 degrees is 90 degrees off the wind, worse than the block's 29.63, so the block's
    axis moves to it: delta = 30 - 90.3685."""
    blk = next(b for b in area.blocks if b.block_id == "blk_0003")
    delta = apply_building(area, building("pc_001", 6.0, 30.0))["blk_0003"]["canyon_axis_deg"]
    assert delta == pytest.approx(30.0 - blk.canyon_axis_deg)


# ── direction properties ──────────────────────────────────────────────────────


@pytest.mark.parametrize("parcel_id", sorted(PARCELS))
@pytest.mark.parametrize("floors", [0.0, 1.0, 2.0, 3.0])
def test_low_rise_never_raises_vci(area: engine.AreaModel, parcel_id: str, floors: float) -> None:
    for o in ORIENTATIONS:
        assert block_vci_change(area, parcel_id, floors, o) <= EPS, (parcel_id, floors, o)


@pytest.mark.parametrize("parcel_id", sorted(PARCELS))
def test_adding_floors_never_raises_vci(area: engine.AreaModel, parcel_id: str) -> None:
    """For every orientation, VCI on the parcel's block never goes up as floors are added."""
    for o in ORIENTATIONS:
        vcis = [block_vci_change(area, parcel_id, float(f), o) for f in range(0, 15)]
        assert all(v <= EPS for v in vcis), (parcel_id, o, vcis)
        assert all(b <= a + EPS for a, b in pairwise(vcis)), (parcel_id, o, vcis)


@pytest.mark.parametrize("parcel_id", sorted(PARCELS))
def test_tall_building_is_never_invisible_to_the_index(area: engine.AreaModel, parcel_id: str) -> None:
    """A 12 floor, 80% footprint building lowers the block's VCI at every orientation. Before, turning it along
    the wind raised W_a by as much as the height lowered O_b, and the worst drop was 0."""
    for o in ORIENTATIONS:
        assert block_vci_change(area, parcel_id, 12.0, o) < -EPS, (parcel_id, o)


@pytest.mark.parametrize("parcel_id", sorted(PARCELS))
def test_orientation_still_changes_the_result_of_a_tall_building(area: engine.AreaModel, parcel_id: str) -> None:
    """Orientation modulates the effect: across the wind costs more than along it, and the spread is real."""
    changes = [block_vci_change(area, parcel_id, 12.0, o) for o in ORIENTATIONS]
    assert max(changes) - min(changes) > 1.0
    # A building along the wind costs exactly its height and length terms; no orientation does better.
    assert max(changes) == pytest.approx(changes[ORIENTATIONS.index(120.0)])


def test_flag_threshold_still_applies(area: engine.AreaModel) -> None:
    """The ventilation flag is raised for a tall building turned across the wind (drop >= threshold)."""
    r = engine.rescore(area, [building("pc_001", 12.0, 30.0)], COSTS)
    assert r.worst_vci_drop >= SETTINGS.vci_drop_threshold
    assert not r.ventilation_ok
