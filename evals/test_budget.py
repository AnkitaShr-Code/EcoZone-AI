"""Budget: greedy and the search never exceed the planner's budget."""

import json

from ecozone_contract import InterventionChange
from ecozone_engine.settings import SETTINGS
from evalkit.bench import Bench
from evalkit.cases import AreaCases
from evalkit.results import Recorder


def test_greedy_never_exceeds_budget(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    over: list[str] = []
    for rc in cases.repair:
        run = bench.greedy_for(rc)
        r = run.portfolio.result
        quick_share = 100 * r.quick_win_cost_inr / rc.budget_inr
        rec.measure(
            "budget.greedy",
            rc.id,
            {
                "budget_inr": rc.budget_inr,
                "cost_inr": round(r.cost_inr),
                "sites": len(run.portfolio.changes),
                "quick_win_share_requested_pct": rc.quick_win_share_pct,
                "quick_win_share_spent_pct": round(quick_share, 1),
                "acs_before": r.before.acs,
                "acs_after": r.after.acs,
            },
        )
        if r.cost_inr > rc.budget_inr:
            over.append(f"{rc.id}: {r.cost_inr} > {rc.budget_inr}")
    assert not over, over


def test_greedy_cost_matches_its_changes(bench: Bench, cases: AreaCases) -> None:
    for rc in cases.repair:
        p = bench.greedy_for(rc).portfolio
        assert bench.rescore(list(p.changes)).cost_inr == p.result.cost_inr


def test_search_never_exceeds_budget(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    problems: list[str] = []
    for rc in cases.repair:
        run = bench.repair_search(rc)
        best = run.result.best
        events = [json.loads(raw) for raw in run.events]
        candidates = [ev["candidate"] for ev in events if ev["type"] == "candidate"]
        rec.measure(
            "budget.search",
            rc.id,
            {"budget_inr": rc.budget_inr, "best_cost_inr": best.cost_inr, "candidates": len(candidates)},
            "fake LLM",
        )
        if best.cost_inr > rc.budget_inr:
            problems.append(f"{rc.id}: best {best.cost_inr} > {rc.budget_inr}")
        # The engine's own cost for the chosen changes, not the rounded number the candidate carries.
        changes = [bench.change(ch.site_id, ch.quantity) for ch in best.changes if isinstance(ch, InterventionChange)]
        cost = bench.rescore(changes).cost_inr
        if cost > rc.budget_inr:
            problems.append(f"{rc.id}: engine cost of the best plan {cost} > {rc.budget_inr}")
        # Every candidate shown as valid is inside the budget; the ones over it are flagged, not hidden.
        for cand in candidates:
            if cand["valid"] and cand["costInr"] > rc.budget_inr:
                problems.append(f"{rc.id}: valid candidate {cand['id']} costs {cand['costInr']}")
    assert not problems, problems


def test_search_returns_a_valid_plan(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    """The plan the search hands back is one the planner can use: inside the budget, the quick-win share met and the
    ventilation check passed (the loop marks a plan that is not with `valid: false` and a reason)."""
    rows: dict[str, object] = {}
    invalid: list[str] = []
    for rc in cases.repair:
        best = bench.repair_search(rc).result.best
        rows[rc.id] = {"valid": best.valid, "source": best.source, "reason": best.invalid_reason}
        if not best.valid:
            invalid.append(f"{rc.id}: {best.invalid_reason}")
    rec.measure("budget.search_validity", "best_plan", rows, "fake LLM")
    assert not invalid, invalid


def test_quick_win_gap_of_the_greedy_plan(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    """Diagnostic for the validity check: how far under the quick-win share the greedy plan ends, and whether a site
    that would close the gap was left out. Informational, no assertion."""
    for rc in cases.repair:
        run = bench.greedy_for(rc)
        r = run.portfolio.result
        target = rc.budget_inr * rc.quick_win_share_pct / 100
        chosen = {ch.site_id for ch in run.portfolio.changes}
        spare = rc.budget_inr - r.cost_inr
        left = sorted(
            (s.quantity_min * bench.costs[s.kind].inr, s.site_id)  # pyright: ignore[reportArgumentType]
            for s in bench.area.sites
            if not s.rejected and s.site_id not in chosen and s.time_to_benefit in SETTINGS.quick_win_ttb
        )
        gap = max(0.0, target - r.quick_win_cost_inr)
        closes = [sid for cost, sid in left if cost >= gap and cost <= spare]
        rec.measure(
            "budget.quick_win_gap",
            rc.id,
            {
                "target_inr": round(target),
                "quick_win_cost_inr": round(r.quick_win_cost_inr),
                "shortfall_inr": round(gap),
                "spare_budget_inr": round(spare),
                "unchosen_quick_win_sites": len(left),
                "cheapest_unchosen_quick_win_inr": round(left[0][0]) if left else None,
                "unchosen_sites_that_fit_the_spare_budget_and_close_the_gap": len(closes),
            },
            "greedy at these inputs",
        )
