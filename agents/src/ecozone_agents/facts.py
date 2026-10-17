"""The engine values an explanation may cite, as one JSON-able dict (the "tool results" of agents/RULES.md).

The writer model is shown exactly this dict, the output guard builds its allowed set from it, and the
template fallback is filled from it, so the three can never disagree. Scores are rounded to 1 decimal
and rupees to whole rupees, as the API does, so the planner sees the same numbers everywhere.
"""

from collections import Counter
from collections.abc import Mapping, Sequence

import ecozone_contract as c
import ecozone_engine as e

from . import to_contract as tc
from .catalog import ParcelInfo, SiteBrief
from .text import DRIVER_LABEL, INDEX_WORDS

Facts = dict[str, object]


def _scores(s: e.AreaScores) -> dict[str, float]:
    return {
        "acs": tc.score(s.acs),
        "pss": tc.score(s.pss),
        "hei": tc.score(s.hei),
        "gcs": tc.score(s.gcs),
        "vci": tc.score(s.vci),
    }


def _drivers(tags: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(tags))


def _driver_labels(tags: Sequence[str]) -> dict[str, str]:
    return {tag: DRIVER_LABEL.get(tag, tag) for tag in tags}


def _design(d: c.BuildingDesign) -> dict[str, float]:
    return {
        "floors": d.floors,
        "footprint_pct": d.footprint_pct,
        "green_pct": d.green_pct,
        "orientation_deg": d.orientation_deg,
    }


def risk_facts(risk: e.RiskInfo) -> dict[str, object]:
    words, direction = INDEX_WORDS[risk.index]
    return {
        "label": risk.label,
        "index": risk.index,
        "index_words": words,
        "direction": direction,
        "change": tc.score(risk.change),
    }


def repair_facts(
    *,
    result: e.AreaResultData,
    changes: Sequence[e.Change],
    sites: Mapping[str, SiteBrief],
    budget_inr: float | None = None,
    quick_win_share_pct: float | None = None,
    unit_costs: c.UnitCosts | None = None,
    greedy: tuple[float, float] | None = None,
    plan_source: str | None = None,
    gemini_beat_greedy: bool | None = None,
    rejected: Sequence[c.RejectedOption] = (),
    rejected_total: int = 0,
    rounds: int | None = None,
    reference_date: str | None = None,
) -> Facts:
    """Facts for a Repair plan: from a finished search, or from any change set (the explain route)."""
    interventions = [
        {
            "site_id": ch.site_id,
            "kind": ch.kind,
            "name": sites[ch.site_id].name if ch.site_id in sites else ch.site_id,
            "quantity": ch.quantity,
            "time_to_benefit": sites[ch.site_id].time_to_benefit if ch.site_id in sites else None,
        }
        for ch in changes
    ]
    counts = Counter(ch.kind for ch in changes)
    drivers = _drivers(result.drivers)
    facts: Facts = {
        "mode": "repair",
        "before": _scores(result.before),
        "after": _scores(result.after),
        "cost_inr": tc.inr(result.cost_inr),
        "quick_win_cost_inr": tc.inr(result.quick_win_cost_inr),
        "wait_points_covered": result.wait_points_covered,
        "blocks_worse": result.blocks_worse,
        "ventilation_ok": result.ventilation_ok,
        "interventions": interventions,
        "counts_by_kind": {kind: counts[kind] for kind in sorted(counts)},
        "drivers": drivers,
        "driver_labels": _driver_labels(drivers),
    }
    if budget_inr is not None:
        facts["budget_inr"] = tc.inr(budget_inr)
    if quick_win_share_pct is not None:
        facts["quick_win_share_pct"] = quick_win_share_pct
    if unit_costs is not None:
        facts["unit_costs_inr"] = {kind: tc.inr(getattr(unit_costs, kind).inr) for kind in tc.KINDS}
    if greedy is not None:
        facts["greedy"] = {"acs": tc.score(greedy[0]), "cost_inr": tc.inr(greedy[1])}
    if plan_source is not None:
        facts["plan_source"] = plan_source
    if gemini_beat_greedy is not None:
        facts["gemini_beat_greedy"] = gemini_beat_greedy
    if rejected_total:
        facts["rejected_total"] = rejected_total
        facts["rejected"] = [{"site_id": r.site_id, "driver": r.driver, "reason": r.reason} for r in rejected]
    if rounds is not None:
        facts["rounds"] = rounds
    if reference_date:
        facts["reference_date"] = reference_date
    return facts


def protect_facts(
    *,
    proposal: c.BuildingDesign,
    result: e.AreaResultData,
    parcel: ParcelInfo | None,
    parcel_id: str,
    options: Sequence[c.DesignOption] = (),
    keep_floor_area_pct: float | None = None,
    min_floor_area_pct: float | None = None,
    rounds: int | None = None,
    reference_date: str | None = None,
) -> Facts:
    """Facts for a Protect proposal, with options A, B and C once a design search has run."""
    drivers = _drivers(result.drivers)
    facts: Facts = {
        "mode": "protect",
        "parcel": {
            "id": parcel_id,
            "name": parcel.name if parcel else parcel_id,
            "road_width_m": parcel.road_width_m if parcel and parcel.road_width_m is not None else None,
            "neighbour_height_m": parcel.neighbour_height_m
            if parcel and parcel.neighbour_height_m is not None
            else None,
        },
        "proposal": _design(proposal),
        "risk": risk_facts(result.risk) if result.risk else None,
        "before": _scores(result.before),
        "after": _scores(result.after),
        "blocks_worse": result.blocks_worse,
        "drivers": drivers,
        "driver_labels": _driver_labels(drivers),
    }
    if options:
        facts["options"] = [
            {
                "key": o.key,
                "title": o.title,
                "design": _design(o.design),
                "floor_area_pct": o.candidate.floor_area_pct,
                "worst_change": o.candidate.risk.change if o.candidate.risk else o.candidate.score,
                "risk_label": o.candidate.risk.label if o.candidate.risk else None,
                "trade_off": o.trade_off,
            }
            for o in options
        ]
    if keep_floor_area_pct is not None:
        facts["keep_floor_area_pct"] = keep_floor_area_pct
    if min_floor_area_pct is not None:
        facts["min_floor_area_pct"] = min_floor_area_pct
    if rounds is not None:
        facts["rounds"] = rounds
    if reference_date:
        facts["reference_date"] = reference_date
    return facts
