"""Read-only views of a loaded area: summary, layers, hotspots, single-site results, baselines."""

from __future__ import annotations

from types import MappingProxyType

from ._stub import NotImplementedYetError
from .model import (
    AreaModel,
    AreaSummaryData,
    BaselineData,
    Feature,
    HotspotData,
    LayerName,
    Scores,
    SingleSiteData,
    UnitCosts,
)


def summary(area: AreaModel) -> AreaSummaryData:
    """Return area-level summary data, including baseline scores from the precomputed baseline."""
    if area.meta is None or area.baseline is None:
        raise NotImplementedYetError("summary", "WP5a")
    m = area.meta
    b = area.baseline
    return AreaSummaryData(
        area_id=area.area_id,
        name=m.name,
        city=m.city,
        bundle_version=area.bundle_version,
        bbox_xy=m.bbox_xy,
        reference_date=m.reference_date,
        shade_times=m.shade_times,
        baseline=b.area,
        wind_from_deg=m.wind_from_deg,
        metres_per_floor=m.metres_per_floor,
        counts=m.counts,
        buildings_by_height_source=m.buildings_by_height_source,
        derived_footpath_chunks=m.derived_footpath_chunks,
        skipped_steps=m.skipped_steps,
        attribution=m.attribution,
    )


def layer(area: AreaModel, name: LayerName) -> list[Feature]:
    """Return map features for the named layer in EPSG:32643."""
    if area.meta is None:
        raise NotImplementedYetError("layer", "WP5a")

    if name == "blocks":
        return [
            Feature(
                id=b.block_id,
                geometry=b.geometry,
                properties=MappingProxyType(
                    {
                        "area_m2": b.area_m2,
                        "scores": Scores(vci=b.vci, hei=b.hei, gcs=b.gcs, pss=b.pss),
                        "priority": b.priority,
                        "priority_class": b.priority_class,
                        "built_form": b.built_form,
                        "wait_weight": b.wait_weight,
                        "drivers": b.drivers,
                    }
                ),
            )
            for b in area.blocks
        ]

    if name == "segments":
        return [
            Feature(
                id=c.chunk_id,
                geometry=c.geometry,
                properties=MappingProxyType(
                    {
                        "road_class": c.road_class,
                        "length_m": c.length_m,
                        "block_id": c.block_id,
                        "near_wait": c.near_wait,
                        "shaded": c.shade,
                    }
                ),
            )
            for c in area.chunks
        ]

    if name == "buildings":
        return [
            Feature(
                id=b.building_id,
                geometry=b.geometry,
                properties=MappingProxyType(
                    {
                        "height_m": b.height_m,
                        "height_source": b.height_source,
                    }
                ),
            )
            for b in area.buildings
        ]

    if name == "wait_points":
        return [
            Feature(
                id=w.wait_id,
                geometry=w.geometry,
                properties=MappingProxyType(
                    {
                        "kind": w.kind,
                        "name": w.name,
                        "weight": w.weight,
                    }
                ),
            )
            for w in area.wait_points
        ]

    if name == "parcels":
        return [
            Feature(
                id=p.parcel_id,
                geometry=p.geometry,
                properties=MappingProxyType(
                    {
                        "block_id": p.block_id,
                        "name": p.name,
                        "area_m2": p.area_m2,
                        "road_name": p.road_name,
                        "road_width_m": p.road_width_m,
                        "street_bearing_deg": p.street_bearing_deg,
                        "neighbour_height_m": p.neighbour_height_m,
                    }
                ),
            )
            for p in area.parcels
        ]

    if name == "sites":
        return [
            Feature(
                id=s.site_id,
                geometry=s.geometry,
                properties=MappingProxyType(
                    {
                        "kind": s.kind,
                        "name": s.name,
                        "quantity": s.quantity_max,
                        "time_to_benefit": s.time_to_benefit,
                        "wait_point_id": s.wait_point_id,
                        "h_w": s.h_w,
                    }
                ),
            )
            for s in area.sites
        ]

    raise ValueError(f"Unknown layer: {name}")  # pyright: ignore[reportReturnType]


def hotspots(area: AreaModel, top: int) -> list[HotspotData]:
    """Return the top-n blocks by priority, highest first."""
    if area.meta is None:
        raise NotImplementedYetError("hotspots", "WP5a")
    ranked = sorted(area.blocks, key=lambda b: (-b.priority, b.block_id))
    result: list[HotspotData] = []
    for rank, b in enumerate(ranked[:top], start=1):
        cx, cy = b.geometry.centroid.coords[0]
        result.append(
            HotspotData(
                rank=rank,
                block_id=b.block_id,
                priority=b.priority,
                priority_class=b.priority_class,
                scores=Scores(vci=b.vci, hei=b.hei, gcs=b.gcs, pss=b.pss),
                drivers=b.drivers,
                centroid_xy=(cx, cy),
            )
        )
    return result


def single_site(area: AreaModel, site_id: str, unit_costs: UnitCosts) -> SingleSiteData:
    raise NotImplementedYetError("single_site", "WP5b")


def compute_baselines(area: AreaModel) -> BaselineData:
    """Return precomputed baseline scores; already computed by load_bundle."""
    if area.baseline is None:
        raise NotImplementedYetError("compute_baselines", "WP5a")
    return area.baseline
