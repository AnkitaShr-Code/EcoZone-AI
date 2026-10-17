"""Ventilation guard: a plan that drops a block's VCI by the threshold or more is flagged invalid, nothing else."""

import ecozone_engine as e
from ecozone_engine.settings import SETTINGS
from evalkit.bench import Bench, building_change
from evalkit.cases import AreaCases, Design
from evalkit.results import Recorder

THRESHOLD = SETTINGS.vci_drop_threshold


def block_level_drop(r: e.AreaResultData) -> float:
    return max((b.before.vci - b.after.vci for b in r.blocks), default=0.0)


def _designs(bench: Bench, cases: AreaCases) -> dict[str, e.AreaResultData]:
    out: dict[str, e.AreaResultData] = {}
    for g in cases.guard_designs:
        out[f"guard:{g.parcel_id}"] = bench.rescore([building_change(g.parcel_id, g.design)])
    for pc in cases.protect:
        for floors in cases.floors_ladder:
            d = Design(floors, pc.proposal.footprint_pct, pc.proposal.green_pct, pc.proposal.orientation_deg)
            out[f"{pc.parcel_id}@{floors}f"] = bench.rescore([building_change(pc.parcel_id, d)])
    return out


def test_flag_follows_the_block_level_vci_drop(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    results = _designs(bench, cases)
    bad: list[str] = []
    flagged = 0
    for label, r in results.items():
        drop = block_level_drop(r)
        flagged += not r.ventilation_ok
        if r.ventilation_ok != (drop < THRESHOLD):
            bad.append(f"{label}: block-level drop {drop:.4f}, ventilation_ok={r.ventilation_ok}")
        if abs(r.worst_vci_drop - max(drop, 0.0)) > 1e-9:
            bad.append(f"{label}: worst_vci_drop {r.worst_vci_drop} != block-level {drop}")
    rec.measure(
        "ventilation.flag",
        "building_designs",
        {"designs": len(results), "flagged": flagged, "threshold": THRESHOLD, "inconsistent": len(bad)},
    )
    assert not bad, bad[:10]


def test_tall_guard_designs_are_flagged_invalid(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    rows = {}
    for g in cases.guard_designs:
        r = bench.rescore([building_change(g.parcel_id, g.design)])
        rows[g.parcel_id] = {"worst_vci_drop": round(r.worst_vci_drop, 2), "ventilation_ok": r.ventilation_ok}
    rec.measure("ventilation.guard", "tall_designs", rows, f"flag threshold {THRESHOLD}")
    unflagged = {p: v for p, v in rows.items() if v["ventilation_ok"] or v["worst_vci_drop"] < THRESHOLD}
    assert not unflagged, unflagged


def test_greedy_plans_pass_the_guard(bench: Bench, cases: AreaCases) -> None:
    for rc in cases.repair:
        r = bench.greedy_for(rc).portfolio.result
        assert r.ventilation_ok, f"greedy:{rc.id} is flagged (worst drop {r.worst_vci_drop})"
        assert block_level_drop(r) < THRESHOLD


def test_low_impact_plan_is_not_flagged(bench: Bench, cases: AreaCases) -> None:
    r = bench.rescore([bench.change(sid) for sid in cases.typical_portfolio])
    assert r.ventilation_ok and r.worst_vci_drop < THRESHOLD


def test_risk_label_reflects_the_parcels_block(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    """The label follows the worst change on the parcel's block (contract RiskInfo): 10+ MODERATE, 25+ HIGH."""

    def expected(change: float) -> str:
        if change >= SETTINGS.risk_high_min:
            return "HIGH"
        return "MODERATE" if change >= SETTINGS.risk_moderate_min else "LOW"

    rows: dict[str, dict[str, object]] = {}
    mismatches = 0
    designs = [(g.parcel_id, g.design, f"guard:{g.parcel_id}") for g in cases.guard_designs]
    designs += [(p.parcel_id, p.proposal, f"proposal:{p.parcel_id}") for p in cases.protect]
    for parcel_id, design, label in designs:
        r = bench.rescore([building_change(parcel_id, design)])
        parcel = next(p for p in bench.area.parcels if p.parcel_id == parcel_id)
        blk = next(b for b in r.blocks if b.block_id == parcel.block_id)
        worst = max(
            blk.before.vci - blk.after.vci,
            blk.after.hei - blk.before.hei,
            blk.before.gcs - blk.after.gcs,
            blk.before.pss - blk.after.pss,
            0.0,
        )
        assert r.risk is not None
        rows[label] = {
            "block_worst_change": round(worst, 2),
            "expected_label": expected(worst),
            "engine_label": r.risk.label,
            "engine_change": round(r.risk.change, 3),
        }
        mismatches += expected(worst) != r.risk.label or abs(r.risk.change - worst) > 1e-9
        mismatches += dict(r.parcel_risk).get(parcel_id) != r.risk
    rec.measure("ventilation.risk_label", "parcel_block_vs_engine", rows)
    assert mismatches == 0, rows


def test_orientation_sensitivity_of_a_tall_building(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    """Informational: worst block VCI drop of the same tall design at every 15 degree orientation. The design search
    uses orientation as a lever; this shows how far it alone moves the ventilation flag."""
    g = cases.guard_designs[0]
    rows: dict[str, float] = {}
    for deg in range(0, 180, 15):
        d = Design(g.design.floors, g.design.footprint_pct, g.design.green_pct, float(deg))
        rows[f"{deg}"] = round(bench.rescore([building_change(g.parcel_id, d)]).worst_vci_drop, 2)
    rec.measure(
        "ventilation.orientation_sensitivity",
        g.parcel_id,
        rows,
        f"{g.design.floors} floors, {g.design.footprint_pct:g}% footprint, {g.design.green_pct:g}% green; "
        "key = orientation in degrees, value = worst VCI drop",
    )
    assert all(v >= 0 for v in rows.values())
