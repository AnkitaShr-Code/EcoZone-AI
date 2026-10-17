"""Read-only views of a loaded area: summary, layers, hotspots, single-site results, baselines."""

from __future__ import annotations

from ._stub import NotImplementedYetError
from .model import (
    AreaModel,
    AreaSummaryData,
    BaselineData,
    Change,
    Feature,
    HotspotData,
    LayerName,
    SingleSiteData,
    UnitCosts,
)


def summary(area: AreaModel) -> AreaSummaryData:
    raise NotImplementedYetError("summary", "WP5a")


def layer(area: AreaModel, name: LayerName) -> list[Feature]:
    raise NotImplementedYetError("layer", "WP5a")


def hotspots(area: AreaModel, top: int) -> list[HotspotData]:
    raise NotImplementedYetError("hotspots", "WP5a")


def single_site(area: AreaModel, site_id: str, unit_costs: UnitCosts) -> SingleSiteData:
    """Score a site applied alone (WP5b). Calls rescore() — the one code path."""
    from .costs import site_cost
    from .errors import UnknownSiteError
    from .rescore import rescore

    site = next((s for s in area.sites if s.site_id == site_id), None)
    if site is None:
        raise UnknownSiteError(site_id)

    quantity = site.quantity_min  # default to minimum quantity for single-site scoring
    change = Change(kind=site.kind, site_id=site_id, quantity=quantity)  # type: ignore[arg-type]

    result = rescore(area, [change], unit_costs)
    acs_gain = result.after.acs - result.before.acs
    cost = site_cost(area, change, unit_costs)

    reason: str | None = None
    if not result.ventilation_ok:
        reason = f"VCI drops by {result.worst_vci_drop:.1f} points"

    return SingleSiteData(
        site_id=site_id,
        acs_gain=acs_gain,
        cost_inr=cost,
        drivers=result.drivers,
        ventilation_ok=result.ventilation_ok,
        ventilation_reason=reason,
    )


def compute_baselines(area: AreaModel) -> BaselineData:
    raise NotImplementedYetError("compute_baselines", "WP5a")
