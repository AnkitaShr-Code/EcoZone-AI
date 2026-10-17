"""Greedy baseline the AI search is compared against (engine/RULES.md, "Greedy").

Algorithm (engine/RULES.md §Greedy):
1. Separate valid sites into quick-win (weeks/season) and long-term (years).
2. Add quick wins ranked by ACS gain per rupee (tie-break by site id) until the quick-win spend is
   at least the share of the budget. The last quick win may carry the spend past the share, as long
   as the total stays within budget: the share is a minimum (PLANNING.md "at least the share").
3. Fill the remaining budget with all remaining valid sites by ACS gain per rupee.
4. Skip a site whose marginal ACS gain is <= 0 or which fails the ventilation check.
5. Rescore the final portfolio and return.
"""

from __future__ import annotations

from .costs import is_quick_win, site_cost
from .model import AreaModel, Change, PortfolioData, UnitCosts
from .rescore import rescore
from .settings import SETTINGS as S


def _candidate_sites(area: AreaModel) -> list[tuple[str, str, float]]:
    """(site_id, kind, quantity_min) for all non-rejected sites, sorted by site_id."""
    return [(s.site_id, s.kind, s.quantity_min) for s in sorted(area.sites, key=lambda s: s.site_id) if not s.rejected]


def _score_gain(area: AreaModel, change: Change, unit_costs: UnitCosts) -> tuple[float, float]:
    """(acs_gain, cost_inr) for one site applied alone.  Returns (0, 0) on error."""
    try:
        result = rescore(area, [change], unit_costs)
        cost = site_cost(area, change, unit_costs)
        return result.after.acs - result.before.acs, cost
    except Exception:
        return 0.0, 0.0


def greedy_baseline(
    area: AreaModel, budget_inr: float, unit_costs: UnitCosts, quick_win_share_pct: float
) -> PortfolioData:
    """Return the greedy portfolio and its rescore result."""
    quick_win_budget = budget_inr * quick_win_share_pct / 100.0
    candidates = _candidate_sites(area)

    # Pre-score all valid sites
    scored: list[tuple[float, float, str, str, float]] = []
    for site_id, kind, qty in candidates:
        change = Change(kind=kind, site_id=site_id, quantity=qty)  # type: ignore[arg-type]
        gain, cost = _score_gain(area, change, unit_costs)
        if cost > 0.0:
            scored.append((gain, cost, site_id, kind, qty))

    def sort_key(item: tuple[float, float, str, str, float]) -> tuple[float, str]:
        _gain, cost, site_id, _kind, _qty = item
        return (-(_gain / cost), site_id)

    scored.sort(key=sort_key)

    quick_wins = [
        (c, sid, knd, qty)
        for _g, c, sid, knd, qty in scored
        if is_quick_win(area, Change(kind=knd, site_id=sid, quantity=qty))  # type: ignore[arg-type]
    ]

    chosen: list[Change] = []
    spent = 0.0
    quick_spent = 0.0
    used_ids: set[str] = set()
    current_acs = area.area_baseline.acs

    # ── Phase 1: reach the quick-win share ────────────────────────────────────
    # The share is a minimum, so a quick win is never refused for taking the quick-win spend past
    # it; the loop stops once the share is met. Refusing it left the spend just under the share
    # whenever the leftover was smaller than the cheapest remaining quick win. If the share cannot
    # be reached within the budget, the quick wins that did fit are kept and the plan is returned
    # short; the caller flags it.
    for cost, site_id, kind, qty in quick_wins:
        if quick_spent >= quick_win_budget:
            break
        if site_id in used_ids:
            continue
        if spent + cost > budget_inr:
            continue
        change = Change(kind=kind, site_id=site_id, quantity=qty)  # type: ignore[arg-type]
        # One rescore of the portfolio with the site added gives the marginal gain and the ventilation check.
        try:
            trial = rescore(area, [*chosen, change], unit_costs)
        except Exception:
            continue
        if trial.after.acs - current_acs <= S.greedy_min_gain or not trial.ventilation_ok:
            continue
        chosen.append(change)
        current_acs = trial.after.acs
        spent += cost
        quick_spent += cost
        used_ids.add(site_id)

    # ── Phase 2: fill remaining budget with all sites ─────────────────────────
    for _g, cost, site_id, kind, qty in scored:
        if site_id in used_ids:
            continue
        if spent + cost > budget_inr:
            continue
        change = Change(kind=kind, site_id=site_id, quantity=qty)  # type: ignore[arg-type]
        try:
            trial = rescore(area, [*chosen, change], unit_costs)
        except Exception:
            continue
        if trial.after.acs - current_acs <= S.greedy_min_gain or not trial.ventilation_ok:
            continue
        chosen.append(change)
        current_acs = trial.after.acs
        spent += cost
        used_ids.add(site_id)

    # ── Final rescore of chosen portfolio ─────────────────────────────────────
    final_result = rescore(area, chosen, unit_costs) if chosen else rescore(area, [], unit_costs)

    return PortfolioData(
        changes=tuple(sorted(chosen, key=lambda c: c.site_id)),
        result=final_result,
    )
