"""Cost of a change set from planner unit costs (engine/RULES.md).

Costs are labeled planner input and never called 'price' or 'market rate'.
"""

from __future__ import annotations

from collections.abc import Sequence

from .model import AreaModel, Change, InterventionKind, UnitCosts
from .settings import SETTINGS as S


def site_cost(area: AreaModel, change: Change, unit_costs: UnitCosts) -> float:
    """Cost in INR for one Change (quantity × unit cost INR)."""
    if change.kind == "building":
        return 0.0
    kind: InterventionKind = change.kind  # type: ignore[assignment]
    uc = unit_costs.get(kind)
    if uc is None:
        return 0.0
    return change.quantity * uc.inr


def is_quick_win(area: AreaModel, change: Change) -> bool:
    """True when the change's site has time_to_benefit in the quick-win qualifier set."""
    if change.kind == "building":
        return False
    site = next((s for s in area.sites if s.site_id == change.site_id), None)
    if site is None:
        return False
    return site.time_to_benefit in S.quick_win_ttb


def portfolio_costs(
    area: AreaModel, changes: Sequence[Change], unit_costs: UnitCosts
) -> tuple[float, float]:
    """Return (total_cost_inr, quick_win_cost_inr) for a change set."""
    total = 0.0
    quick = 0.0
    for change in sorted(changes, key=lambda c: c.site_id):
        cost = site_cost(area, change, unit_costs)
        total += cost
        if is_quick_win(area, change):
            quick += cost
    return total, quick
