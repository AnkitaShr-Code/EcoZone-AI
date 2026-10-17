"""Read-only views of a loaded area: summary, layers, hotspots, single-site results, baselines."""

from __future__ import annotations

from dataclasses import dataclass

from .drivers import block_drivers
from .model import (
    AreaModel,
    AreaSummaryData,
    BaselineData,
    BlockRow,
    Change,
    Feature,
    HotspotData,
    LayerName,
    PriorityClass,
    Scores,
    SingleSiteData,
    SiteRow,
    UnitCosts,
)
from .priority import block_priority, wait_weight_sum
from .shade import compute_chunk_shading
from .shadows import tree_positions


def summary(area: AreaModel) -> AreaSummaryData:
    """Area facts from the loaded bundle. Counts come from the tables, so they always match the layers."""
    height_sources = ("osm_height", "osm_levels", "open_buildings", "typology")
    return AreaSummaryData(
        area_id=area.area_id,
        name=area.name,
        city=area.city,
        bundle_version=area.bundle_version,
        bbox_xy=area.bbox_xy,
        reference_date=area.reference_date,
        shade_times=area.shade_times,
        baseline=area.area_baseline,
        wind_from_deg=area.wind_from_deg,
        metres_per_floor=area.metres_per_floor,
        counts={
            "blocks": len(area.blocks),
            "buildings": len(area.buildings),
            "segments": len(area.chunks),
            "wait_points": len(area.wait_points),
            "sites": len(_offered_sites(area)),
            "parcels": len(area.parcels),
        },
        buildings_by_height_source={
            src: sum(1 for b in area.buildings if b.height_source == src) for src in height_sources
        },
        derived_footpath_chunks=area.derived_footpath_chunks,
        skipped_steps=area.skipped_steps,
        attribution=area.attribution,
    )


def _offered_sites(area: AreaModel) -> list[SiteRow]:
    """Sites a planner may pick: everything except canopy-rule rejects, in id order (engine/RULES.md, Ventilation)."""
    return sorted((s for s in area.sites if not s.rejected), key=lambda s: s.site_id)


def layer(area: AreaModel, name: LayerName) -> list[Feature]:
    """Features of one map layer in id order, with the property keys listed in engine/RULES.md."""
    if name == "blocks":
        return [
            Feature(
                st.block.block_id,
                st.block.geometry,
                {
                    "area_m2": st.block.area_m2,
                    "scores": st.scores,
                    "priority": st.priority,
                    "priority_class": st.priority_class,
                    "built_form": st.block.built_form,
                    "wait_weight": st.wait_weight,
                    "drivers": st.drivers,
                },
            )
            for st in sorted(_block_stats(area), key=lambda st: st.block.block_id)
        ]
    if name == "segments":
        shading = dict(area.baseline_shading) or compute_chunk_shading(area)
        return [
            Feature(
                c.chunk_id,
                c.geometry,
                {
                    "road_name": c.road_name,
                    "road_class": c.road_class,
                    "length_m": c.length_m,
                    "block_id": c.block_id or None,
                    "near_wait": c.near_wait,
                    "shaded": shading[c.chunk_id],
                },
            )
            for c in sorted(area.chunks, key=lambda c: c.chunk_id)
        ]
    if name == "buildings":
        return [
            Feature(b.building_id, b.geometry, {"height_m": b.height_m, "height_source": b.height_source})
            for b in sorted(area.buildings, key=lambda b: b.building_id)
        ]
    if name == "wait_points":
        return [
            Feature(w.wait_id, w.geometry, {"kind": w.kind, "name": w.name, "weight": w.weight})
            for w in sorted(area.wait_points, key=lambda w: w.wait_id)
        ]
    if name == "parcels":
        return [
            Feature(
                p.parcel_id,
                p.geometry,
                {
                    "block_id": p.block_id,
                    "name": p.name,
                    "area_m2": p.area_m2,
                    "road_name": p.road_name,
                    "road_width_m": p.road_width_m,
                    "street_bearing_deg": p.street_bearing_deg,
                    "neighbour_height_m": p.neighbour_height_m,
                },
            )
            for p in sorted(area.parcels, key=lambda p: p.parcel_id)
        ]
    return [_site_feature(s) for s in _offered_sites(area)]


def _site_feature(site: SiteRow) -> Feature:
    """A site with its default quantity: the minimum, the quantity `single_site` and the greedy baseline score."""
    properties: dict[str, object] = {
        "kind": site.kind,
        "name": site.name,
        "quantity": site.quantity_min,
        "time_to_benefit": site.time_to_benefit,
        "wait_point_id": site.wait_point_id,
        "h_w": site.H_W,
    }
    if site.kind == "tree_row":
        # The positions `rescore` shades with at this quantity (shadows.tree_positions).
        properties["points"] = tuple(tree_positions(site.geometry, round(site.quantity_min)))
    return Feature(site.site_id, site.geometry, properties)


@dataclass(frozen=True)
class _BlockStat:
    block: BlockRow
    scores: Scores
    priority: float
    priority_class: PriorityClass
    wait_weight: float
    drivers: tuple[str, ...]


def _block_stats(area: AreaModel) -> list[_BlockStat]:
    """Baseline priority, class and drivers for every block, ranked: priority descending, then id."""
    baselines = dict(area.block_baselines)
    wait_list = list(area.wait_points)
    zero = Scores(vci=0.0, hei=0.0, gcs=0.0, pss=0.0)

    scored = [
        (block_priority(b, baselines.get(b.block_id, zero), wait_list), b)
        for b in sorted(area.blocks, key=lambda r: r.block_id)
    ]
    ranked = sorted(scored, key=lambda x: (-x[0], x[1].block_id))
    n = len(ranked)
    cutoff_high = ranked[max(0, n // 3 - 1)][0] if n >= 3 else (ranked[0][0] if n else 0.0)
    cutoff_low = ranked[min(n - 1, (2 * n) // 3)][0] if n >= 3 else 0.0

    def _class(p: float) -> PriorityClass:
        if p >= cutoff_high:
            return "high"
        if p <= cutoff_low:
            return "low"
        return "medium"

    stats: list[_BlockStat] = []
    for priority, b in ranked:
        sc = baselines.get(b.block_id, zero)
        weight_sum = wait_weight_sum(b.geometry, wait_list)
        stats.append(
            _BlockStat(
                block=b,
                scores=sc,
                priority=priority,
                priority_class=_class(priority),
                wait_weight=weight_sum,
                drivers=block_drivers(
                    pss=sc.pss, i_s=b.I_s, roof_albedo=b.roof_albedo, d_green=b.d_green, wait_weight_sum=weight_sum
                ),
            )
        )
    return stats


def hotspots(area: AreaModel, top: int) -> list[HotspotData]:
    """Return the top-n blocks by priority, highest first (PLANNING.md §Priority)."""
    result: list[HotspotData] = []
    for rank, st in enumerate(_block_stats(area)[:top], start=1):
        cx, cy = st.block.geometry.centroid.coords[0]
        result.append(
            HotspotData(
                rank=rank,
                block_id=st.block.block_id,
                priority=st.priority,
                priority_class=st.priority_class,
                scores=st.scores,
                drivers=st.drivers,
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
