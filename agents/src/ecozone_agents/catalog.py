"""The candidate sites and parcels the agents reason about, read through the engine port.

Single-site results come from `single_site` (the engine), never from agent code. The catalog is
what the proposer is shown and what the scorer checks site ids against (docs/PLANNING.md, tool
contract `list_candidate_sites`).
"""

from dataclasses import dataclass
from typing import cast

import ecozone_engine as e

from .ports import EnginePort

QUICK_WIN_TTB = frozenset({"weeks", "season"})
"""Time-to-benefit values that count as helping this summer (docs/PLANNING.md, Repair step 3)."""


@dataclass(frozen=True)
class SiteBrief:
    """What a site is, from the sites layer alone (no scoring)."""

    id: str
    kind: e.InterventionKind
    name: str
    quantity: float
    time_to_benefit: str
    wait_point_id: str | None

    @property
    def quick_win(self) -> bool:
        return self.time_to_benefit in QUICK_WIN_TTB


@dataclass(frozen=True)
class SiteInfo(SiteBrief):
    """A site with the engine's single-site result."""

    acs_gain: float
    cost_inr: float
    drivers: tuple[str, ...]
    ventilation_ok: bool
    ventilation_reason: str | None


@dataclass(frozen=True)
class ParcelInfo:
    id: str
    name: str
    block_id: str | None
    road_name: str | None
    road_width_m: float | None
    neighbour_height_m: float | None


def _brief(feature: e.Feature) -> SiteBrief:
    p = feature.properties
    return SiteBrief(
        id=feature.id,
        kind=cast(e.InterventionKind, p["kind"]),
        name=str(p.get("name") or feature.id),
        quantity=float(cast(float, p["quantity"])),
        time_to_benefit=str(p["time_to_benefit"]),
        wait_point_id=cast("str | None", p.get("wait_point_id")),
    )


def describe_sites(engine: EnginePort, area: e.AreaModel) -> dict[str, SiteBrief]:
    """Every site's kind, name and time to benefit, in id order. Cheap: no scoring."""
    return {f.id: _brief(f) for f in sorted(engine.layer(area, "sites"), key=lambda f: f.id)}


def load_sites(engine: EnginePort, area: e.AreaModel, unit_costs: e.UnitCosts) -> dict[str, SiteInfo]:
    """Every site with its single-site engine result at these unit costs, in id order."""
    sites: dict[str, SiteInfo] = {}
    for site_id, brief in describe_sites(engine, area).items():
        single = engine.single_site(area, site_id, unit_costs)
        sites[site_id] = SiteInfo(
            **vars(brief),
            acs_gain=single.acs_gain,
            cost_inr=single.cost_inr,
            drivers=tuple(single.drivers),
            ventilation_ok=single.ventilation_ok,
            ventilation_reason=single.ventilation_reason,
        )
    return sites


def load_parcel(engine: EnginePort, area: e.AreaModel, parcel_id: str) -> ParcelInfo | None:
    for feature in engine.layer(area, "parcels"):
        if feature.id == parcel_id:
            p = feature.properties
            width = p.get("road_width_m")
            neighbour = p.get("neighbour_height_m")
            return ParcelInfo(
                id=feature.id,
                name=str(p.get("name") or feature.id),
                block_id=cast("str | None", p.get("block_id")),
                road_name=cast("str | None", p.get("road_name")),
                road_width_m=float(cast(float, width)) if width is not None else None,
                neighbour_height_m=float(cast(float, neighbour)) if neighbour is not None else None,
            )
    return None
