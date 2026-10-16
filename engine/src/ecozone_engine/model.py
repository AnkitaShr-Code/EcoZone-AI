"""Engine data types: the area model, changes and results.

All results are frozen dataclasses (engine/RULES.md, "Typed"). `api` and `agents` convert
them to `contract` models in their `to_contract.py`; the engine never imports `contract`.
Field names follow docs/PLANNING.md terms; geometry is EPSG:32643, metres.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

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


@dataclass(frozen=True)
class AreaModel:
    """One area loaded from a bundle. Immutable; never mutated by scoring (engine/RULES.md, "Pure").

    The engine owner (WP5a) adds the arrays and STRtree indexes; fields below are the minimum
    the API needs to identify the area.
    """

    area_id: str
    bundle_version: str


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
    area_id: str
    name: str
    city: str
    bundle_version: str
    bbox_xy: tuple[float, float, float, float]
    reference_date: str
    shade_times: tuple[ShadeTime, ...]
    baseline: AreaScores
    counts: Mapping[str, int] = field(default_factory=dict[str, int])
    data_gaps: Mapping[str, int] = field(default_factory=dict[str, int])
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
