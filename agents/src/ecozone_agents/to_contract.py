"""Engine ↔ contract conversions used by the agents (ENGINEERING_RULES.md §4: one module per package).

Rounding for planner-facing values happens here and in `candidates`: scores to 1 decimal, rupees to
whole rupees. Comparisons inside the search use the engine's raw values.
"""

from collections.abc import Sequence

import ecozone_contract as c
import ecozone_engine as e

KINDS: tuple[e.InterventionKind, ...] = ("tree_row", "shade", "depave", "pocket_green", "cool_roof")


def score(value: float) -> float:
    return round(value, 1)


def inr(value: float) -> float:
    return float(round(value))


def engine_unit_costs(costs: c.UnitCosts) -> dict[e.InterventionKind, e.UnitCost]:
    return {
        kind: e.UnitCost(
            unit=getattr(costs, kind).unit, inr=getattr(costs, kind).inr, source=getattr(costs, kind).source
        )
        for kind in KINDS
    }


def intervention_change(kind: e.InterventionKind, site_id: str, quantity: float) -> e.Change:
    return e.Change(kind=kind, site_id=site_id, quantity=quantity)


def building_change(parcel_id: str, design: c.BuildingDesign) -> e.Change:
    """Params sorted by name, as engine/RULES.md specifies."""
    params = (
        ("floors", float(design.floors)),
        ("footprint_pct", design.footprint_pct),
        ("green_pct", design.green_pct),
        ("orientation_deg", design.orientation_deg),
    )
    return e.Change(kind="building", site_id=parcel_id, quantity=1.0, params=params)


def engine_change(change: c.InterventionChange | c.BuildingChange) -> e.Change:
    if isinstance(change, c.BuildingChange):
        return building_change(change.site_id, change.design)
    return e.Change(kind=change.kind, site_id=change.site_id, quantity=change.quantity)


def engine_changes(changes: Sequence[c.InterventionChange | c.BuildingChange]) -> list[e.Change]:
    return [engine_change(ch) for ch in changes]


def contract_change(change: e.Change) -> c.InterventionChange | c.BuildingChange:
    if change.kind == "building":
        p = dict(change.params)
        design = c.BuildingDesign(
            floors=round(p["floors"]),
            footprint_pct=p["footprint_pct"],
            green_pct=p["green_pct"],
            orientation_deg=p["orientation_deg"],
        )
        return c.BuildingChange(kind="building", site_id=change.site_id, design=design)
    return c.InterventionChange(kind=change.kind, site_id=change.site_id, quantity=change.quantity)


def risk(info: e.RiskInfo) -> c.RiskInfo:
    return c.RiskInfo(label=info.label, index=info.index, change=score(info.change))
