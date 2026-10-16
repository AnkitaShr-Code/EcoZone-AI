"""Area summary and the map layers (GET /api/areas/{area}, /layers/{name}, /shadows)."""

from typing import Literal

from pydantic import Field

from .common import (
    BuiltForm,
    ContractModel,
    DriverTag,
    HeightSource,
    LonLat,
    PriorityClass,
    ShadeByTime,
    ShadeTime,
    WaitPointKind,
)
from .geo import LineStringGeometry, PointGeometry, PolygonGeometry


class Scores(ContractModel):
    """Index scores, 0–100, rounded to 1 decimal."""

    vci: float = Field(description="Ventilation Corridor Index; higher is better.")
    hei: float = Field(description="Heat Exposure Index; lower is better.")
    gcs: float = Field(description="Green Connectivity Score; higher is better.")
    pss: float = Field(description="Pedestrian Shade Score; higher is better.")


class AreaScores(Scores):
    acs: float = Field(description="Area Cooling Score, exposure-weighted; higher is better.")


class UnitCost(ContractModel):
    """Planner unit cost for one intervention type. Defaults are always labelled planner input."""

    unit: str = Field(description="What one unit is, for example 'tree' or 'm²'.")
    inr: float = Field(description="Rupees per unit.")
    source: str = Field(description="Citation for the default; 'planner' once the planner edits it.")
    source_url: str | None = None


class UnitCosts(ContractModel):
    """Keyed by intervention type, spelled exactly as InterventionType so `unitCosts[site.type]` works."""

    tree_row: UnitCost = Field(alias="tree_row")
    shade: UnitCost
    depave: UnitCost
    pocket_green: UnitCost = Field(alias="pocket_green")
    cool_roof: UnitCost = Field(alias="cool_roof")


class AreaCounts(ContractModel):
    blocks: int
    buildings: int
    segments: int
    wait_points: int
    sites: int
    parcels: int


class DataGaps(ContractModel):
    """Where values came from fallbacks; the data-caveat line in briefs is generated from this."""

    buildings_by_height_source: dict[HeightSource, int]
    derived_footpath_segments: int = Field(description="Footpath chunks derived from road edges, not OSM sidewalks.")
    skipped_steps: list[str] = Field(description="Optional pipeline steps not run, for example 'earth_engine'.")


class EngineConstants(ContractModel):
    """Engine values the UI displays or passes back; the UI never computes scores from them."""

    wind_from_deg: float
    metres_per_floor: float


class AreaSummary(ContractModel):
    id: str
    name: str
    city: str
    bundle_version: str
    bbox: tuple[float, float, float, float] = Field(description="West, south, east, north in WGS84.")
    center: LonLat
    reference_date: str = Field(description="ISO date of the shade reference day.")
    shade_times: list[ShadeTime]
    baseline: AreaScores
    counts: AreaCounts
    data_gaps: DataGaps
    unit_cost_defaults: UnitCosts
    engine: EngineConstants
    mock: bool = Field(description="True only when served by the mock adapter (a snapshot or mock rescore).")
    attribution: str = Field(
        description="Data attribution, including the OSM ODbL notice; shown on the map and briefs."
    )


# ---------- layer properties ----------


class BlockProps(ContractModel):
    id: str
    area_m2: float
    scores: Scores
    priority: float
    priority_class: PriorityClass
    built_form: BuiltForm
    wait_weight: float
    drivers: list[DriverTag]
    centroid: LonLat


class SegmentProps(ContractModel):
    """A 10 m footpath chunk (engine/RULES.md, chunks)."""

    id: str
    road: str | None
    road_class: str
    length_m: float
    block: str | None
    near_wait: bool
    shaded: ShadeByTime


class BuildingProps(ContractModel):
    id: str
    height_m: float
    height_source: HeightSource


class WaitPointProps(ContractModel):
    id: str
    type: WaitPointKind
    name: str | None
    weight: float


class ParcelProps(ContractModel):
    """A vacant plot that Protect can test a proposed building on."""

    id: str
    block_id: str
    name: str
    area_m2: float
    center: LonLat
    road_name: str | None
    road_width_m: float
    street_bearing_deg: float
    neighbour_height_m: float


class EmptyProps(ContractModel):
    pass


# ---------- features and layers ----------


class BlockFeature(ContractModel):
    type: Literal["Feature"]
    geometry: PolygonGeometry
    properties: BlockProps


class SegmentFeature(ContractModel):
    type: Literal["Feature"]
    geometry: LineStringGeometry
    properties: SegmentProps


class BuildingFeature(ContractModel):
    type: Literal["Feature"]
    geometry: PolygonGeometry
    properties: BuildingProps


class WaitPointFeature(ContractModel):
    type: Literal["Feature"]
    geometry: PointGeometry
    properties: WaitPointProps


class ParcelFeature(ContractModel):
    type: Literal["Feature"]
    geometry: PolygonGeometry
    properties: ParcelProps


class ShadowFeature(ContractModel):
    type: Literal["Feature"]
    geometry: PolygonGeometry
    properties: EmptyProps


class BlockLayer(ContractModel):
    type: Literal["FeatureCollection"]
    features: list[BlockFeature]


class SegmentLayer(ContractModel):
    type: Literal["FeatureCollection"]
    features: list[SegmentFeature]


class BuildingLayer(ContractModel):
    type: Literal["FeatureCollection"]
    features: list[BuildingFeature]


class WaitPointLayer(ContractModel):
    type: Literal["FeatureCollection"]
    features: list[WaitPointFeature]


class ParcelLayer(ContractModel):
    type: Literal["FeatureCollection"]
    features: list[ParcelFeature]


class ShadowLayer(ContractModel):
    type: Literal["FeatureCollection"]
    features: list[ShadowFeature]
