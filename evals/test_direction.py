"""Direction: more shade, trees or green never move an index the wrong way; buildings cannot clear the air;
cost grows with quantity. Cross-package versions of the engine's own tests, on the real bundle's ids."""

from itertools import pairwise

import pytest

import ecozone_engine as e
from evalkit.bench import KINDS, Bench, building_change
from evalkit.cases import AreaCases, Design
from evalkit.results import Recorder

EPS = 1e-9


def wrong_way(r: e.AreaResultData) -> list[str]:
    """Per block, a repair intervention must not lower VCI, GCS or PSS, nor raise HEI."""
    out: list[str] = []
    for b in r.blocks:
        for name, delta, worse in (
            ("vci", b.after.vci - b.before.vci, lambda d: d < -EPS),
            ("hei", b.after.hei - b.before.hei, lambda d: d > EPS),
            ("gcs", b.after.gcs - b.before.gcs, lambda d: d < -EPS),
            ("pss", b.after.pss - b.before.pss, lambda d: d < -EPS),
        ):
            if worse(delta):
                out.append(f"{b.block_id} {name} {delta:+.6f}")
    if r.after.acs < r.before.acs - EPS:
        out.append(f"area acs {r.after.acs - r.before.acs:+.6f}")
    return out


@pytest.mark.parametrize("kind", KINDS)
def test_repair_intervention_never_moves_an_index_the_wrong_way(
    kind: str, bench: Bench, cases: AreaCases, rec: Recorder
) -> None:
    problems: list[str] = []
    checked = 0
    for sid in cases.direction_sites.get(kind, ()):
        qmin, qmax = bench.site_quantities(sid)
        for q in (qmin, qmax):
            r = bench.rescore([bench.change(sid, q)])
            checked += 1
            problems += [f"{sid}@{q:g}: {p}" for p in wrong_way(r)]
    rec.measure("direction.repair", kind, {"checks": checked, "wrong_way": len(problems)})
    assert checked > 0, f"cases.yaml lists no {kind} site for this area"
    assert not problems, problems[:10]


@pytest.mark.parametrize("kind", KINDS)
def test_more_quantity_never_scores_worse(kind: str, bench: Bench, cases: AreaCases) -> None:
    for sid in cases.direction_sites.get(kind, ()):
        qmin, qmax = bench.site_quantities(sid)
        if qmax <= qmin:
            continue
        lo, hi = bench.rescore([bench.change(sid, qmin)]), bench.rescore([bench.change(sid, qmax)])
        assert hi.after.acs >= lo.after.acs - EPS, f"{sid}: acs {lo.after.acs} at {qmin} but {hi.after.acs} at {qmax}"
        by_block = {b.block_id: b for b in lo.blocks}
        for b in hi.blocks:
            ref = by_block[b.block_id].after
            assert b.after.hei <= ref.hei + EPS, f"{sid} {b.block_id}: hei rises with quantity"
            assert b.after.gcs >= ref.gcs - EPS, f"{sid} {b.block_id}: gcs falls with quantity"
            assert b.after.pss >= ref.pss - EPS, f"{sid} {b.block_id}: pss falls with quantity"


def test_cost_is_monotonic_in_quantity(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    """Cost = quantity x the planner's unit cost, so it grows strictly with quantity and has no jumps."""
    checked = 0
    for kind in KINDS:
        for sid in cases.direction_sites.get(kind, ()):
            qmin, qmax = bench.site_quantities(sid)
            if qmax <= qmin:
                continue
            ladder = [qmin, (qmin + qmax) / 2, qmax]
            costs = [bench.rescore([bench.change(sid, q)]).cost_inr for q in ladder]
            assert costs == sorted(costs) and len(set(costs)) == len(costs), f"{sid}: {costs}"
            unit = bench.costs[kind].inr  # pyright: ignore[reportArgumentType]
            for q, cost in zip(ladder, costs, strict=True):
                assert cost == pytest.approx(q * unit), f"{sid}: cost {cost} for quantity {q}"
            checked += 1
    rec.measure("direction.cost", "monotonic_in_quantity", {"sites_checked": checked})
    assert checked > 0


def test_cost_of_a_portfolio_is_the_sum_of_its_sites(bench: Bench, cases: AreaCases) -> None:
    changes = [bench.change(sid) for sid in cases.typical_portfolio]
    total = bench.rescore(changes).cost_inr
    parts = sum(bench.rescore([ch]).cost_inr for ch in changes)
    assert total == pytest.approx(parts)


# ---------- buildings ----------


def _with_floors(d: Design, floors: int) -> Design:
    return Design(floors, d.footprint_pct, d.green_pct, d.orientation_deg)


def _max_vci_rise(r: e.AreaResultData) -> float:
    return max((b.after.vci - b.before.vci for b in r.blocks), default=0.0)


def test_tall_building_cannot_improve_ventilation(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    """A building at least as tall as its street is wide: no block's VCI rises, and VCI falls with every extra floor."""
    mpf = bench.info.meta.get("metres_per_floor", 3.0)
    problems: list[str] = []
    worst_rise = 0.0
    for pc in cases.protect:
        parcel = next(p for p in bench.area.parcels if p.parcel_id == pc.parcel_id)
        tall = [f for f in cases.floors_ladder if f * mpf >= parcel.road_width_m]
        previous: dict[str, float] = {}
        for floors in tall:
            r = bench.rescore([building_change(pc.parcel_id, _with_floors(pc.proposal, floors))])
            rise = _max_vci_rise(r)
            worst_rise = max(worst_rise, rise)
            if rise > EPS:
                problems.append(f"{pc.parcel_id} {floors} floors: a block's VCI rises by {rise:.3f}")
            now = {b.block_id: b.after.vci for b in r.blocks}
            for bid, v in now.items():
                if bid in previous and v > previous[bid] + EPS:
                    problems.append(f"{pc.parcel_id} {bid}: VCI {previous[bid]:.3f} -> {v:.3f} with more floors")
            previous = now
    rec.measure("direction.building", "tall_building_max_vci_rise", worst_rise)
    assert not problems, problems[:10]


def test_any_building_cannot_improve_ventilation(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    """Whatever its height, adding a building to a block must not raise the block's VCI."""
    rises: dict[str, float] = {}
    for pc in cases.protect:
        for floors in cases.floors_ladder:
            r = bench.rescore([building_change(pc.parcel_id, _with_floors(pc.proposal, floors))])
            rise = _max_vci_rise(r)
            if rise > EPS:
                rises[f"{pc.parcel_id}@{floors}f"] = rise
    rec.measure("direction.building", "any_building_vci_rises", rises)
    assert not rises, rises


def test_building_effect_grows_with_height(bench: Bench, cases: AreaCases) -> None:
    """Worst VCI drop on the parcel's block never shrinks as floors are added."""
    for pc in cases.protect:
        drops = [
            bench.rescore([building_change(pc.parcel_id, _with_floors(pc.proposal, f))]).worst_vci_drop
            for f in cases.floors_ladder
        ]
        assert all(b >= a - EPS for a, b in pairwise(drops)), f"{pc.parcel_id}: {drops}"
