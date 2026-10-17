"""Protect risk label: measured on the block that contains the proposed building's parcel (PLANNING.md "Risk label").

Fixture: engine/tests/fixtures/tiny. pc_001 is on blk_0003, pc_002 on blk_0002, pc_003 on blk_0004.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import ecozone_engine as engine
from ecozone_engine.model import Change, Scores, UnitCost, UnitCosts
from ecozone_engine.priority import risk_label
from ecozone_engine.settings import SETTINGS

TINY = Path(__file__).parent / "fixtures" / "tiny"
COSTS: UnitCosts = {"shade": UnitCost(unit="m2", inr=2_000.0, source="test")}


@pytest.fixture(scope="module")
def area() -> engine.AreaModel:
    return engine.load_bundle(TINY)


def building(parcel_id: str, floors: float, orientation_deg: float = 30.0) -> Change:
    return Change(
        kind="building",
        site_id=parcel_id,
        quantity=1.0,
        params=(
            ("floors", floors),
            ("footprint_pct", 80.0),
            ("green_pct", 5.0),
            ("orientation_deg", orientation_deg),
        ),
    )


def block_worst_change(r: engine.AreaResultData, block_id: str) -> float:
    blk = next(b for b in r.blocks if b.block_id == block_id)
    return max(
        blk.before.vci - blk.after.vci,
        blk.after.hei - blk.before.hei,
        blk.before.gcs - blk.after.gcs,
        blk.before.pss - blk.after.pss,
        0.0,
    )


# ── risk_label on block scores: thresholds and the index that drives it ──────


def test_risk_label_thresholds_come_from_settings() -> None:
    """Worst change is the largest of VCI drop, HEI rise, GCS drop, PSS drop; just under a threshold is the lower
    label, at the threshold the higher one."""
    before = Scores(vci=70.0, hei=50.0, gcs=40.0, pss=30.0)

    def after_vci_drop(drop: float) -> Scores:
        return Scores(vci=70.0 - drop, hei=50.0, gcs=40.0, pss=30.0)

    just_under = SETTINGS.risk_moderate_min - 0.01
    assert risk_label(before, after_vci_drop(just_under)).label == "LOW"
    assert risk_label(before, after_vci_drop(SETTINGS.risk_moderate_min)).label == "MODERATE"
    assert risk_label(before, after_vci_drop(SETTINGS.risk_high_min - 0.01)).label == "MODERATE"
    high = risk_label(before, after_vci_drop(SETTINGS.risk_high_min))
    assert (high.label, high.index, high.change) == ("HIGH", "vci", SETTINGS.risk_high_min)


@pytest.mark.parametrize(
    ("after", "index", "change"),
    [
        (Scores(vci=70.0, hei=62.0, gcs=40.0, pss=30.0), "hei", 12.0),
        (Scores(vci=70.0, hei=50.0, gcs=21.0, pss=30.0), "gcs", 19.0),
        (Scores(vci=70.0, hei=50.0, gcs=40.0, pss=5.0), "pss", 25.0),
    ],
)
def test_risk_label_picks_the_worst_index(after: Scores, index: str, change: float) -> None:
    before = Scores(vci=70.0, hei=50.0, gcs=40.0, pss=30.0)
    info = risk_label(before, after)
    assert (info.index, info.change) == (index, change)
    assert info.label == ("HIGH" if change >= SETTINGS.risk_high_min else "MODERATE")


def test_risk_label_improvements_are_not_a_risk() -> None:
    before = Scores(vci=70.0, hei=50.0, gcs=40.0, pss=30.0)
    better = Scores(vci=80.0, hei=40.0, gcs=50.0, pss=40.0)
    info = risk_label(before, better)
    assert (info.label, info.change) == ("LOW", 0.0)


# ── rescore: the label is the parcel's block, not the area ────────────────────


def test_risk_is_the_worst_change_on_the_parcels_block(area: engine.AreaModel) -> None:
    """12 floors on pc_001 (blk_0003) at orientation 30 drops that block's VCI by about 37 points, which averaged
    over the six blocks of the area is under 5. The label follows the block: HIGH."""
    r = engine.rescore(area, [building("pc_001", 12.0)], COSTS)
    block_drop = block_worst_change(r, "blk_0003")
    area_drop = r.before.vci - r.after.vci
    assert block_drop >= SETTINGS.risk_high_min > area_drop
    assert r.risk is not None
    assert r.risk.label == "HIGH"
    assert r.risk.index == "vci"
    assert r.risk.change == pytest.approx(block_drop)
    assert r.parcel_risk == (("pc_001", r.risk),)


def test_each_parcel_gets_its_own_blocks_risk_and_risk_is_the_worst(area: engine.AreaModel) -> None:
    changes = [building("pc_003", 12.0), building("pc_001", 1.0, orientation_deg=90.0)]
    r = engine.rescore(area, changes, COSTS)
    assert [pid for pid, _ in r.parcel_risk] == ["pc_001", "pc_003"]  # sorted by parcel id, not change order
    by_parcel = dict(r.parcel_risk)
    assert by_parcel["pc_003"].change == pytest.approx(block_worst_change(r, "blk_0004"))
    assert by_parcel["pc_001"].change == pytest.approx(block_worst_change(r, "blk_0003"))
    assert by_parcel["pc_003"].label == "HIGH"
    assert by_parcel["pc_001"].label == "LOW"
    assert r.risk == by_parcel["pc_003"]


def test_risk_does_not_depend_on_change_order(area: engine.AreaModel) -> None:
    a = engine.rescore(area, [building("pc_003", 6.0), building("pc_002", 6.0)], COSTS)
    b = engine.rescore(area, [building("pc_002", 6.0), building("pc_003", 6.0)], COSTS)
    assert a.risk == b.risk
    assert a.parcel_risk == b.parcel_risk


def test_risk_threshold_follows_the_block_change(area: engine.AreaModel) -> None:
    """The label is a function of the block change alone (thresholds from settings), over a ladder of heights."""
    for floors in (1.0, 2.0, 6.0, 12.0):
        r = engine.rescore(area, [building("pc_002", floors)], COSTS)
        assert r.risk is not None
        change = block_worst_change(r, "blk_0002")
        expected = (
            "HIGH"
            if change >= SETTINGS.risk_high_min
            else "MODERATE"
            if change >= SETTINGS.risk_moderate_min
            else "LOW"
        )
        assert r.risk.label == expected, (floors, change)
        assert r.risk.change == pytest.approx(change)


def test_no_building_no_risk(area: engine.AreaModel) -> None:
    r = engine.rescore(area, [], COSTS)
    assert r.risk is None
    assert r.parcel_risk == ()
