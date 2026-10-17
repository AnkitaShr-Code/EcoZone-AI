"""Greedy baseline: the quick-win share is a minimum (PLANNING.md "at least the share"), the budget a maximum.

Fixture: engine/tests/fixtures/tiny with the unit costs below. Its quick-win sites at minimum quantity cost
16,000 (two shade structures), 75,050 and 127,850 (depave) and 92,480 (cool roof), so the quick-win spend can only
take certain values and a plan can sit just under a share that the next quick win would carry it past.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import ecozone_engine as engine
from ecozone_engine.model import UnitCost, UnitCosts

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


@pytest.mark.parametrize(
    ("budget_inr", "share_pct"),
    [(150_000.0, 60.0), (400_000.0, 50.0), (250_000.0, 50.0), (300_000.0, 40.0)],
)
def test_quick_win_spend_reaches_the_share(area: engine.AreaModel, budget_inr: float, share_pct: float) -> None:
    """Cases where the old phase 1 stopped short.

    It refused any quick win that would take the quick-win spend over the share, so it ended under the share
    whenever the leftover was smaller than the cheapest remaining quick win (before: 16,000 of 90,000 at
    150,000 / 60%, and 183,530 of 200,000 at 400,000 / 50%). The last quick win may now cross the share.
    """
    plan = engine.greedy_baseline(area, budget_inr, COSTS, share_pct)
    target = budget_inr * share_pct / 100.0
    assert plan.result.quick_win_cost_inr >= target
    assert plan.result.cost_inr <= budget_inr


def test_last_quick_win_may_cross_the_share(area: engine.AreaModel) -> None:
    """At 150,000 / 20% the share is 30,000; the best quick wins per rupee cost more than that, so the plan
    spends more than the share on quick wins and still stays within the budget."""
    plan = engine.greedy_baseline(area, 150_000.0, COSTS, 20.0)
    assert plan.result.quick_win_cost_inr > 30_000.0
    assert plan.result.cost_inr <= 150_000.0


def test_unreachable_share_returns_a_short_plan(area: engine.AreaModel) -> None:
    """A 100% share cannot be met inside 150,000 (no combination of quick wins at minimum quantity adds up to
    it). Greedy still returns its best plan, within budget, with quick-win spend under the target, so the
    caller flags it as below the share exactly as before."""
    budget = 150_000.0
    plan = engine.greedy_baseline(area, budget, COSTS, 100.0)
    assert plan.changes
    assert plan.result.cost_inr <= budget
    assert 0.0 < plan.result.quick_win_cost_inr < budget


def test_zero_share_adds_no_forced_quick_wins(area: engine.AreaModel) -> None:
    """With a 0% share phase 1 does nothing; the plan is the same as a plain best-per-rupee fill."""
    plan = engine.greedy_baseline(area, 150_000.0, COSTS, 0.0)
    assert plan.result.cost_inr <= 150_000.0


@pytest.mark.parametrize("budget_inr", [0.0, 20_000.0, 100_000.0, 150_000.0, 250_000.0, 400_000.0, 1_500_000.0])
@pytest.mark.parametrize("share_pct", [0.0, 20.0, 60.0, 100.0])
def test_budget_is_never_exceeded(area: engine.AreaModel, budget_inr: float, share_pct: float) -> None:
    plan = engine.greedy_baseline(area, budget_inr, COSTS, share_pct)
    assert plan.result.cost_inr <= budget_inr
    assert plan.result.quick_win_cost_inr <= plan.result.cost_inr + 1e-6
    assert plan.result.ventilation_ok


def test_greedy_is_deterministic_for_a_share_that_crosses(area: engine.AreaModel) -> None:
    first = engine.greedy_baseline(area, 400_000.0, COSTS, 50.0)
    second = engine.greedy_baseline(area, 400_000.0, COSTS, 50.0)
    assert first.changes == second.changes
    assert first.result.after.acs == second.result.after.acs
