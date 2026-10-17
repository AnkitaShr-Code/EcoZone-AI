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
    PriorityClass,
    Scores,
    SingleSiteData,
    UnitCosts,
)


def summary(area: AreaModel) -> AreaSummaryData:
    raise NotImplementedYetError("summary", "WP5a")


def layer(area: AreaModel, name: LayerName) -> list[Feature]:
    raise NotImplementedYetError("layer", "WP5a")


def hotspots(area: AreaModel, top: int) -> list[HotspotData]:
    """Return the top-n blocks by priority, highest first (PLANNING.md §Priority)."""
    from .priority import block_priority

    baseline_dict = dict(area.block_baselines)
    wait_list = list(area.wait_points)

    # Compute priority for every block, sorted deterministically
    scored: list[tuple[float, str]] = []
    for b in sorted(area.blocks, key=lambda r: r.block_id):
        sc = baseline_dict.get(b.block_id, Scores(vci=0.0, hei=0.0, gcs=0.0, pss=0.0))
        p = block_priority(b, sc, wait_list)
        scored.append((p, b.block_id))

    ranked = sorted(scored, key=lambda x: (-x[0], x[1]))
    n = len(ranked)
    cutoff_high = ranked[max(0, n // 3 - 1)][0] if n >= 3 else (ranked[0][0] if n else 0.0)
    cutoff_low = ranked[min(n - 1, (2 * n) // 3)][0] if n >= 3 else 0.0

    def _class(p: float) -> PriorityClass:
        if p >= cutoff_high:
            return "high"
        if p <= cutoff_low:
            return "low"
        return "medium"

    result: list[HotspotData] = []
    for rank, (priority, block_id) in enumerate(ranked[:top], start=1):
        blk = next(b for b in area.blocks if b.block_id == block_id)
        sc = baseline_dict.get(block_id, Scores(vci=0.0, hei=0.0, gcs=0.0, pss=0.0))
        cx, cy = blk.geometry.centroid.coords[0]
        result.append(
            HotspotData(
                rank=rank,
                block_id=block_id,
                priority=priority,
                priority_class=_class(priority),
                scores=sc,
                drivers=(),
                centroid_xy=(cx, cy),
            )
        )
    return result


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
    """Return precomputed baseline scores; computed by load_bundle (PLANNING.md §ACS)."""
    return BaselineData(
        blocks=area.block_baselines,
        area=area.area_baseline,
    )
