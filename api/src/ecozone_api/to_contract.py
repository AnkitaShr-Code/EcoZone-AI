"""Engine results → contract models, and contract requests → engine inputs.

The only place rounding and the EPSG:32643 → WGS84 conversion happen (api/RULES.md). Scores are
rounded to 1 decimal, rupees to whole rupees, coordinates to 6 decimals.
"""

from collections.abc import Mapping, Sequence
from typing import Any, cast

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

import ecozone_contract as c
import ecozone_engine as e
from ecozone_contract.area import (
    BlockFeature,
    BuildingFeature,
    ParcelFeature,
    SegmentFeature,
    ShadowFeature,
    WaitPointFeature,
)
from ecozone_contract.common import LayerName, LonLat
from ecozone_contract.runs import RepairSearchRequest

_TO_WGS84 = Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True)

ENGINE_LAYER: dict[LayerName, e.LayerName] = {
    "blocks": "blocks",
    "segments": "segments",
    "buildings": "buildings",
    "waitPoints": "wait_points",
    "parcels": "parcels",
}

ContractLayer = c.BlockLayer | c.SegmentLayer | c.BuildingLayer | c.WaitPointLayer | c.ParcelLayer


def score(value: float) -> float:
    return round(value, 1)


def inr(value: float) -> float:
    return float(round(value))


# ---------- geometry ----------


def _project(coords: np.ndarray[Any, np.dtype[np.float64]]) -> np.ndarray[Any, np.dtype[np.float64]]:
    lon, lat = _TO_WGS84.transform(coords[:, 0], coords[:, 1])  # pyright: ignore[reportUnknownMemberType]
    return np.round(np.column_stack([lon, lat]), 6)


def to_wgs84(geometry: BaseGeometry) -> dict[str, Any]:
    """GeoJSON geometry dict in WGS84, coordinates rounded to 6 decimals."""
    return cast(dict[str, Any], mapping(shapely.transform(geometry, _project)))


def lonlat(xy: tuple[float, float]) -> LonLat:
    lon, lat = _TO_WGS84.transform(xy[0], xy[1])  # pyright: ignore[reportUnknownMemberType]
    return (round(float(lon), 6), round(float(lat), 6))


def _centroid(geometry: BaseGeometry) -> LonLat:
    point = geometry.centroid
    return lonlat((point.x, point.y))


# ---------- scores ----------


def scores(s: e.Scores) -> c.Scores:
    return c.Scores(vci=score(s.vci), hei=score(s.hei), gcs=score(s.gcs), pss=score(s.pss))


def area_scores(s: e.AreaScores) -> c.AreaScores:
    return c.AreaScores(vci=score(s.vci), hei=score(s.hei), gcs=score(s.gcs), pss=score(s.pss), acs=score(s.acs))


def risk(r: e.RiskInfo) -> c.RiskInfo:
    return c.RiskInfo(label=r.label, index=r.index, change=score(r.change))


# ---------- area ----------


def summary(data: e.AreaSummaryData, unit_cost_defaults: c.UnitCosts) -> c.AreaSummary:
    west, south = lonlat((data.bbox_xy[0], data.bbox_xy[1]))
    east, north = lonlat((data.bbox_xy[2], data.bbox_xy[3]))
    counts = data.counts
    return c.AreaSummary(
        id=data.area_id,
        name=data.name,
        city=data.city,
        bundle_version=data.bundle_version,
        bbox=(west, south, east, north),
        center=(round((west + east) / 2, 6), round((south + north) / 2, 6)),
        reference_date=data.reference_date,
        shade_times=list(data.shade_times),
        baseline=area_scores(data.baseline),
        counts=c.AreaCounts(
            blocks=counts.get("blocks", 0),
            buildings=counts.get("buildings", 0),
            segments=counts.get("segments", 0),
            wait_points=counts.get("wait_points", 0),
            sites=counts.get("sites", 0),
            parcels=counts.get("parcels", 0),
        ),
        data_gaps=c.DataGaps.model_validate(
            {
                "buildingsByHeightSource": dict(data.buildings_by_height_source),
                "derivedFootpathSegments": data.derived_footpath_chunks,
                "skippedSteps": list(data.skipped_steps),
            }
        ),
        unit_cost_defaults=unit_cost_defaults,
        engine=c.EngineConstants(wind_from_deg=data.wind_from_deg, metres_per_floor=data.metres_per_floor),
        mock=False,
        attribution=data.attribution,
    )


def _props(feature: e.Feature, layer: LayerName) -> dict[str, Any]:
    p = feature.properties
    if layer == "blocks":
        block_scores = cast(e.Scores, p["scores"])
        return {
            "id": feature.id,
            "areaM2": round(cast(float, p["area_m2"]), 1),
            "scores": scores(block_scores),
            "priority": score(cast(float, p["priority"])),
            "priorityClass": p["priority_class"],
            "builtForm": p["built_form"],
            "waitWeight": round(cast(float, p["wait_weight"]), 3),
            "drivers": list(cast(Sequence[str], p["drivers"])),
            "centroid": _centroid(feature.geometry),
        }
    if layer == "segments":
        return {
            "id": feature.id,
            "road": p["road_name"],
            "roadClass": p["road_class"],
            "lengthM": round(cast(float, p["length_m"]), 1),
            "block": p["block_id"],
            "nearWait": p["near_wait"],
            "shaded": p["shaded"],
        }
    if layer == "buildings":
        return {"id": feature.id, "heightM": round(cast(float, p["height_m"]), 1), "heightSource": p["height_source"]}
    if layer == "waitPoints":
        return {"id": feature.id, "type": p["kind"], "name": p["name"], "weight": p["weight"]}
    return {
        "id": feature.id,
        "blockId": p["block_id"],
        "name": p["name"],
        "areaM2": round(cast(float, p["area_m2"]), 1),
        "center": _centroid(feature.geometry),
        "roadName": p["road_name"],
        "roadWidthM": round(cast(float, p["road_width_m"]), 1),
        "streetBearingDeg": round(cast(float, p["street_bearing_deg"]), 1),
        "neighbourHeightM": round(cast(float, p["neighbour_height_m"]), 1),
    }


_FEATURE: dict[LayerName, type[c.ContractModel]] = {
    "blocks": BlockFeature,
    "segments": SegmentFeature,
    "buildings": BuildingFeature,
    "waitPoints": WaitPointFeature,
    "parcels": ParcelFeature,
}
_LAYER: dict[LayerName, type[ContractLayer]] = {
    "blocks": c.BlockLayer,
    "segments": c.SegmentLayer,
    "buildings": c.BuildingLayer,
    "waitPoints": c.WaitPointLayer,
    "parcels": c.ParcelLayer,
}


def layer(name: LayerName, features: Sequence[e.Feature]) -> ContractLayer:
    model = _FEATURE[name]
    converted = [
        model.model_validate({"type": "Feature", "geometry": to_wgs84(f.geometry), "properties": _props(f, name)})
        for f in features
    ]
    return _LAYER[name].model_validate({"type": "FeatureCollection", "features": converted})


def shadow_layer(polygons: Sequence[BaseGeometry]) -> c.ShadowLayer:
    features = [
        ShadowFeature.model_validate({"type": "Feature", "geometry": to_wgs84(p), "properties": {}})
        for p in polygons
        if not p.is_empty
    ]
    return c.ShadowLayer(type="FeatureCollection", features=features)


def hotspot(h: e.HotspotData) -> c.Hotspot:
    return c.Hotspot.model_validate(
        {
            "rank": h.rank,
            "blockId": h.block_id,
            "priority": score(h.priority),
            "priorityClass": h.priority_class,
            "scores": scores(h.scores),
            "drivers": list(h.drivers),
            "centroid": lonlat(h.centroid_xy),
        }
    )


def site(feature: e.Feature, single: e.SingleSiteData) -> c.Site:
    p = feature.properties
    points = cast(Sequence[tuple[float, float]] | None, p.get("points"))
    h_w = cast(float | None, p.get("h_w"))
    ventilation = {"ok": single.ventilation_ok}
    if not single.ventilation_ok:
        ventilation |= {"driver": "CANOPY_OBSTRUCTION", "reason": single.ventilation_reason}
    return c.Site.model_validate(
        {
            "id": feature.id,
            "type": p["kind"],
            "name": p["name"],
            "geometry": to_wgs84(feature.geometry),
            "points": [lonlat(xy) for xy in points] if points else None,
            "quantity": p["quantity"],
            "timeToBenefit": p["time_to_benefit"],
            "waitPoint": p.get("wait_point_id"),
            "hw": round(h_w, 2) if h_w is not None else None,
            "singleSite": {
                "acsGain": score(single.acs_gain),
                "drivers": list(single.drivers),
                "ventilation": ventilation,
            },
        }
    )


# ---------- changes and results ----------


def unit_costs(costs: c.UnitCosts) -> dict[e.InterventionKind, e.UnitCost]:
    kinds: tuple[e.InterventionKind, ...] = ("tree_row", "shade", "depave", "pocket_green", "cool_roof")
    return {kind: _unit_cost(getattr(costs, kind)) for kind in kinds}


def _unit_cost(cost: c.UnitCost) -> e.UnitCost:
    return e.UnitCost(unit=cost.unit, inr=cost.inr, source=cost.source)


def change(ch: c.InterventionChange | c.BuildingChange) -> e.Change:
    if isinstance(ch, c.BuildingChange):
        d = ch.design
        params = (
            ("floors", float(d.floors)),
            ("footprint_pct", d.footprint_pct),
            ("green_pct", d.green_pct),
            ("orientation_deg", d.orientation_deg),
        )
        return e.Change(kind="building", site_id=ch.site_id, quantity=1.0, params=params)
    return e.Change(kind=ch.kind, site_id=ch.site_id, quantity=ch.quantity)


def changes(chs: Sequence[c.InterventionChange | c.BuildingChange]) -> list[e.Change]:
    return [change(ch) for ch in chs]


def contract_change(ch: e.Change) -> c.InterventionChange | c.BuildingChange:
    if ch.kind == "building":
        p = dict(ch.params)
        design = c.BuildingDesign(
            floors=round(p["floors"]),
            footprint_pct=p["footprint_pct"],
            green_pct=p["green_pct"],
            orientation_deg=p["orientation_deg"],
        )
        return c.BuildingChange(kind="building", site_id=ch.site_id, design=design)
    return c.InterventionChange(kind=ch.kind, site_id=ch.site_id, quantity=ch.quantity)


def area_result(r: e.AreaResultData) -> c.AreaResult:
    parcel_risk: Mapping[str, c.RiskInfo] | None = (
        {pid: risk(info) for pid, info in r.parcel_risk} if r.parcel_risk else None
    )
    return c.AreaResult.model_validate(
        {
            "before": area_scores(r.before),
            "after": area_scores(r.after),
            "blocks": [c.BlockResult(id=b.block_id, before=scores(b.before), after=scores(b.after)) for b in r.blocks],
            "segments": dict(r.chunks),
            "ventilationOk": r.ventilation_ok,
            "worstVciDrop": score(r.worst_vci_drop),
            "waitPointsCovered": r.wait_points_covered,
            "costInr": inr(r.cost_inr),
            "quickWinCostInr": inr(r.quick_win_cost_inr),
            "drivers": list(r.drivers),
            "blocksWorse": r.blocks_worse,
            "risk": risk(r.risk) if r.risk else None,
            "parcelRisk": parcel_risk,
        }
    )


def greedy_candidate(portfolio: e.PortfolioData, request: RepairSearchRequest) -> c.Candidate:
    """The greedy plan as a search candidate (round 0), so the app shows it beside Gemini's."""
    cost = inr(portfolio.result.cost_inr)
    within = cost <= request.budget_inr
    return c.Candidate(
        id="greedy",
        round=0,
        source="greedy",
        label="Greedy baseline",
        changes=[contract_change(ch) for ch in portfolio.changes],
        score=score(portfolio.result.after.acs),
        cost_inr=cost,
        valid=within and portfolio.result.ventilation_ok,
        invalid_reason=None if within else "Over budget",
    )
