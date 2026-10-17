"""Engine data types: the area model, changes and results.

All results are frozen dataclasses (engine/RULES.md, "Typed"). `api` and `agents` convert
them to `contract` models in their `to_contract.py`; the engine never imports `contract`.
Field names follow docs/PLANNING.md terms; geometry is EPSG:32643, metres.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, cast

from shapely.geometry.base import BaseGeometry

ShadeTime = Literal["13:00", "15:00", "16:00"]
InterventionKind = Literal["tree_row", "shade", "depave", "pocket_green", "cool_roof"]
ChangeKind = InterventionKind | Literal["building"]
IndexKey = Literal["vci", "hei", "gcs", "pss"]
LayerName = Literal["blocks", "segments", "buildings", "wait_points", "parcels", "sites"]
PriorityClass = Literal["high", "medium", "low"]
RiskLabel = Literal["LOW", "MODERATE", "HIGH"]
ShadeByTime = tuple[bool, bool, bool]
"""Shade state per reference time, in the order of the area's shade times."""


# ---------------------------------------------------------------------------
# Bundle row types — one frozen dataclass per table, populated by io.py
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SunEntry:
    """Sun position for one reference time, from meta.json."""

    time: ShadeTime
    altitude_deg: float
    azimuth_deg: float


@dataclass(frozen=True)
class AreaMeta:
    """Scalar metadata from meta.json."""

    area_id: str
    name: str
    city: str
    bundle_version: str
    bbox_xy: tuple[float, float, float, float]
    reference_date: str
    shade_times: tuple[ShadeTime, ...]
    sun: tuple[SunEntry, ...]
    wind_from_deg: float
    v_ref: float  # 95th-percentile building volume (for T_m in HEI)
    attribution: str
    counts: Mapping[str, int]
    buildings_by_height_source: Mapping[str, int]
    derived_footpath_chunks: int
    skipped_steps: tuple[str, ...]
    metres_per_floor: float


@dataclass(frozen=True)
class BlockRow:
    """One row from blocks.parquet with computed index scores added at load time."""

    block_id: str
    area_m2: float
    geometry: BaseGeometry
    # Precomputed bundle attributes (PLANNING.md §Terms and what changes them)
    i_s: float  # impervious share % (150 m buffer)
    g_c: float  # vegetation share % (150 m buffer)
    g_buf: float  # green share % (300 m buffer)
    d_green: float  # distance to nearest green patch (m)
    d_water: float  # distance to nearest upwind water/park (m)
    h_w: float  # height-to-width ratio of the block's canyon
    canyon_axis_deg: float
    l_built: float  # longest unbroken built run along wind line (m)
    v: float  # total building volume in block (m³)
    roof_albedo: float  # area-weighted roof albedo
    wait_weight: float  # sum of waiting-point weights within 150 m (from pipeline)
    built_form: str  # "dense_low_rise" or "other"
    coverage: float
    median_footprint_m2: float
    median_floors: float
    # Scores computed at load time (engine/RULES.md WP5a)
    vci: float = 0.0
    hei: float = 0.0
    gcs: float = 0.0
    pss: float = 0.0
    priority: float = 0.0
    priority_class: PriorityClass = "medium"
    drivers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChunkRow:
    """One 10 m footpath chunk from chunks.parquet."""

    chunk_id: str
    geometry: BaseGeometry  # LineString in EPSG:32643
    block_id: str
    length_m: float
    near_wait: bool
    bearing_deg: float
    road_class: str
    # Shade state per reference time, computed at load time
    shade: ShadeByTime = (False, False, False)
    pss: float = 0.0


@dataclass(frozen=True)
class BuildingRow:
    """One row from buildings.parquet."""

    building_id: str
    geometry: BaseGeometry  # Polygon footprint in EPSG:32643
    height_m: float
    block_id: str
    roof_albedo: float
    height_source: str


@dataclass(frozen=True)
class SiteRow:
    """One candidate Repair site from sites.parquet."""

    site_id: str
    kind: InterventionKind
    name: str
    geometry: BaseGeometry
    quantity_min: float
    quantity_max: float
    rejected: bool
    rule: str
    wait_point_id: str | None
    h_w: float
    block_id: str
    time_to_benefit: str


@dataclass(frozen=True)
class WaitPointRow:
    """One waiting point from wait_points.parquet."""

    wait_id: str
    kind: str
    name: str
    weight: float
    geometry: BaseGeometry


@dataclass(frozen=True)
class ParcelRow:
    """One Protect parcel from parcels.parquet."""

    parcel_id: str
    block_id: str
    area_m2: float
    road_name: str | None
    road_width_m: float
    street_bearing_deg: float
    neighbour_height_m: float
    name: str
    geometry: BaseGeometry


# ---------------------------------------------------------------------------
# AreaModel — the single immutable in-memory area
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AreaModel:
    """One area loaded from a bundle. Immutable; never mutated by scoring (engine/RULES.md, "Pure").

    `area_id` and `bundle_version` identify the model; all heavy fields are excluded from
    hash/compare so lightweight instances can be constructed in tests with just the two ids.
    """

    area_id: str
    bundle_version: str

    # Metadata from meta.json
    meta: AreaMeta | None = field(default=None, hash=False, compare=False, repr=False)

    # Bundle tables (empty tuples until load_bundle populates them)
    blocks: tuple[BlockRow, ...] = field(default=(), hash=False, compare=False, repr=False)
    chunks: tuple[ChunkRow, ...] = field(default=(), hash=False, compare=False, repr=False)
    buildings: tuple[BuildingRow, ...] = field(default=(), hash=False, compare=False, repr=False)
    sites: tuple[SiteRow, ...] = field(default=(), hash=False, compare=False, repr=False)
    wait_points: tuple[WaitPointRow, ...] = field(default=(), hash=False, compare=False, repr=False)
    parcels: tuple[ParcelRow, ...] = field(default=(), hash=False, compare=False, repr=False)

    # O(1) id→index lookups into the above tuples
    block_index: Mapping[str, int] = field(
        default_factory=lambda: cast(dict[str, int], {}), hash=False, compare=False, repr=False
    )
    chunk_index: Mapping[str, int] = field(
        default_factory=lambda: cast(dict[str, int], {}), hash=False, compare=False, repr=False
    )
    site_index: Mapping[str, int] = field(
        default_factory=lambda: cast(dict[str, int], {}), hash=False, compare=False, repr=False
    )
    parcel_index: Mapping[str, int] = field(
        default_factory=lambda: cast(dict[str, int], {}), hash=False, compare=False, repr=False
    )

    # Spatial indexes (STRtree, None before load_bundle)
    building_tree: object = field(default=None, hash=False, compare=False, repr=False)
    chunk_tree: object = field(default=None, hash=False, compare=False, repr=False)

    # Precomputed baseline (populated by load_bundle; None on a stub instance)
    baseline: BaselineData | None = field(default=None, hash=False, compare=False, repr=False)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scores:
    vci: float
    hei: float
    gcs: float
    pss: float


@dataclass(frozen=True)
class AreaScores:
    vci: float
    hei: float
    gcs: float
    pss: float
    acs: float


@dataclass(frozen=True)
class UnitCost:
    """Planner unit cost for one intervention type; `source` cites where the default came from."""

    unit: str
    inr: float
    source: str


UnitCosts = Mapping[InterventionKind, UnitCost]


@dataclass(frozen=True)
class Change:
    """One change to an area: an intervention on a site (Repair) or a building on a parcel (Protect)."""

    kind: ChangeKind
    site_id: str
    quantity: float
    params: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class RiskInfo:
    label: RiskLabel
    index: IndexKey
    change: float


@dataclass(frozen=True)
class BlockResult:
    block_id: str
    before: Scores
    after: Scores


@dataclass(frozen=True)
class AreaResultData:
    """Result of `rescore`. Mirrors the contract's AreaResult before rounding."""

    before: AreaScores
    after: AreaScores
    blocks: tuple[BlockResult, ...]
    chunks: tuple[tuple[str, ShadeByTime], ...]
    """Chunks whose shade changed, with their new state, sorted by chunk id."""
    ventilation_ok: bool
    worst_vci_drop: float
    wait_points_covered: int
    cost_inr: float
    quick_win_cost_inr: float
    drivers: tuple[str, ...]
    blocks_worse: int
    risk: RiskInfo | None = None
    parcel_risk: tuple[tuple[str, RiskInfo], ...] = ()


@dataclass(frozen=True)
class HotspotData:
    rank: int
    block_id: str
    priority: float
    priority_class: PriorityClass
    scores: Scores
    drivers: tuple[str, ...]
    centroid_xy: tuple[float, float]


@dataclass(frozen=True)
class SingleSiteData:
    """The engine's result for one site on its own (contract `Site.singleSite`)."""

    site_id: str
    acs_gain: float
    cost_inr: float
    drivers: tuple[str, ...]
    ventilation_ok: bool
    ventilation_reason: str | None = None


@dataclass(frozen=True)
class PortfolioData:
    changes: tuple[Change, ...]
    result: AreaResultData


@dataclass(frozen=True)
class AreaSummaryData:
    """Area facts for the contract's AreaSummary; the API adds unit-cost defaults from config."""

    area_id: str
    name: str
    city: str
    bundle_version: str
    bbox_xy: tuple[float, float, float, float]
    reference_date: str
    shade_times: tuple[ShadeTime, ...]
    baseline: AreaScores
    wind_from_deg: float
    metres_per_floor: float
    counts: Mapping[str, int] = field(default_factory=dict[str, int])
    """Keys: blocks, buildings, segments (chunks), wait_points, sites, parcels."""
    buildings_by_height_source: Mapping[str, int] = field(default_factory=dict[str, int])
    """Keys: osm_height, osm_levels, open_buildings, typology (pipeline height chain)."""
    derived_footpath_chunks: int = 0
    """Chunks whose footpath was derived from a road edge, not an OSM sidewalk."""
    skipped_steps: tuple[str, ...] = ()
    attribution: str = ""


@dataclass(frozen=True)
class BaselineData:
    """Baseline scores per block and for the area, as the pipeline stores them in the bundle."""

    blocks: tuple[tuple[str, Scores], ...]
    area: AreaScores


@dataclass(frozen=True)
class Feature:
    """A map feature in EPSG:32643; `api` converts the geometry to WGS84 GeoJSON."""

    id: str
    geometry: BaseGeometry
    properties: Mapping[str, object]
