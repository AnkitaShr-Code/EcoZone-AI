"""Engine data types: the area model, changes and results.

All results are frozen dataclasses (engine/RULES.md, "Typed"). `api` and `agents` convert
them to `contract` models in their `to_contract.py`; the engine never imports `contract`.
Field names follow docs/PLANNING.md terms; geometry is EPSG:32643, metres.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from shapely import STRtree
from shapely.geometry.base import BaseGeometry

from .settings import SETTINGS

ShadeTime = Literal["13:00", "15:00", "16:00"]
InterventionKind = Literal["tree_row", "shade", "depave", "pocket_green", "cool_roof"]
ChangeKind = InterventionKind | Literal["building"]
IndexKey = Literal["vci", "hei", "gcs", "pss"]
LayerName = Literal["blocks", "segments", "buildings", "wait_points", "parcels", "sites"]
PriorityClass = Literal["high", "medium", "low"]
RiskLabel = Literal["LOW", "MODERATE", "HIGH"]
ShadeByTime = tuple[bool, bool, bool]
"""Shade state per reference time, in the order of the area's shade times."""


# ── Per-row data loaded from the bundle (WP5a) ────────────────────────────────


@dataclass(frozen=True)
class SunEntry:
    time: ShadeTime
    altitude_deg: float
    azimuth_deg: float


@dataclass(frozen=True)
class BlockRow:
    block_id: str
    geometry: BaseGeometry
    area_m2: float
    building_count: int
    coverage: float
    median_footprint_m2: float
    median_floors: float
    built_form: str
    I_s: float  # impervious share 0-100
    G_c: float  # green cover share 0-100
    G_buf: float  # green share in 300 m buffer 0-100
    d_green: float  # distance to nearest green patch (m)
    d_water: float  # distance to nearest upwind water/park (m)
    H_W: float  # street height-to-width ratio
    canyon_axis_deg: float
    L_built: float  # longest built-up run along wind line (m)
    V: float  # building volume (m³)
    roof_albedo: float  # area-weighted roof albedo


@dataclass(frozen=True)
class BuildingRow:
    building_id: str
    geometry: BaseGeometry
    height_m: float
    block_id: str
    height_source: str = "typology"  # osm_height, osm_levels, open_buildings or typology


@dataclass(frozen=True)
class ChunkRow:
    chunk_id: str
    geometry: BaseGeometry  # LineString (10 m footpath chunk)
    block_id: str
    length_m: float
    near_wait: bool
    road_name: str | None = None
    road_class: str = ""


@dataclass(frozen=True)
class SiteRow:
    site_id: str
    kind: str  # InterventionKind literal
    geometry: BaseGeometry
    block_id: str | None
    quantity_min: float
    quantity_max: float
    rule: str
    rejected: bool
    wait_point_id: str | None
    H_W: float | None
    time_to_benefit: str  # 'weeks', 'season', or 'years'
    name: str = ""


@dataclass(frozen=True)
class WaitPointRow:
    wait_id: str
    geometry: BaseGeometry
    kind: str
    weight: float
    name: str | None = None


@dataclass(frozen=True)
class ParcelRow:
    parcel_id: str
    block_id: str
    area_m2: float
    road_width_m: float
    street_bearing_deg: float
    neighbour_height_m: float
    geometry: BaseGeometry
    name: str = ""
    road_name: str | None = None


# ── AreaModel (WP5a adds arrays and STRtree indexes) ──────────────────────────


@dataclass(frozen=True)
class AreaModel:
    """One area loaded from a bundle. Immutable; never mutated by scoring (engine/RULES.md, "Pure")."""

    area_id: str
    bundle_version: str

    # ── Scalar meta ───────────────────────────────────────────────────────────
    V_ref: float = 0.0
    wind_from_deg: float = 0.0
    name: str = ""
    city: str = ""
    bbox_xy: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    reference_date: str = ""
    shade_times: tuple[ShadeTime, ...] = ()
    metres_per_floor: float = SETTINGS.metres_per_floor
    derived_footpath_chunks: int = 0
    skipped_steps: tuple[str, ...] = ()
    attribution: str = ""

    # ── Sun table (sorted by time) ────────────────────────────────────────────
    sun: tuple[SunEntry, ...] = ()

    # ── Row data (sorted by id) ───────────────────────────────────────────────
    blocks: tuple[BlockRow, ...] = ()
    buildings: tuple[BuildingRow, ...] = ()
    chunks: tuple[ChunkRow, ...] = ()
    sites: tuple[SiteRow, ...] = ()
    wait_points: tuple[WaitPointRow, ...] = ()
    parcels: tuple[ParcelRow, ...] = ()

    # ── Baseline scores keyed by block_id ─────────────────────────────────────
    block_baselines: tuple[tuple[str, Scores], ...] = ()
    area_baseline: AreaScores = field(default_factory=lambda: AreaScores(vci=0.0, hei=0.0, gcs=0.0, pss=0.0, acs=0.0))

    # ── STRtrees: excluded from hash and comparison ───────────────────────────
    block_tree: STRtree = field(default_factory=lambda: STRtree([]), hash=False, compare=False, repr=False)
    building_tree: STRtree = field(default_factory=lambda: STRtree([]), hash=False, compare=False, repr=False)
    chunk_tree: STRtree = field(default_factory=lambda: STRtree([]), hash=False, compare=False, repr=False)


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
