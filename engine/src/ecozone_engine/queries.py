"""Read-only views of a loaded area: summary, layers, hotspots, single-site results, baselines."""

from __future__ import annotations

from ._stub import NotImplementedYetError
from .model import (
    AreaModel,
    AreaSummaryData,
    BaselineData,
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
    raise NotImplementedYetError("single_site", "WP5b")


def compute_baselines(area: AreaModel) -> BaselineData:
    raise NotImplementedYetError("compute_baselines", "WP5a")
