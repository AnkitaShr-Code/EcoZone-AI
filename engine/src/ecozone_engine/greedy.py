"""Greedy baseline the AI search is compared against (engine/RULES.md, "Greedy")."""

from __future__ import annotations

from ._stub import NotImplementedYetError
from .model import AreaModel, PortfolioData, UnitCosts


def greedy_baseline(
    area: AreaModel, budget_inr: float, unit_costs: UnitCosts, quick_win_share_pct: float
) -> PortfolioData:
    raise NotImplementedYetError("greedy_baseline", "WP5b")
