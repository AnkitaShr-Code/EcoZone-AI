"""Repair: hotspots, candidate sites, changes and the rescore result (POST /api/areas/{area}/rescore)."""

from typing import Annotated, Literal

from pydantic import Field

from .area import AreaScores, Scores, UnitCosts
from .common import ContractModel, DriverTag, InterventionType, LonLat, PriorityClass, ShadeByTime, TimeToBenefit
from .geo import SiteGeometry
from .protect import BuildingDesign, RiskInfo


class Hotspot(ContractModel):
    rank: int
    block_id: str
    priority: float
    priority_class: PriorityClass
    scores: Scores
    drivers: list[DriverTag]
    centroid: LonLat


class VentilationCheck(ContractModel):
    ok: bool
    driver: DriverTag | None = Field(default=None, description="Set when ok is false, for example CANOPY_OBSTRUCTION.")
    reason: str | None = Field(
        default=None, description="Plain-language reason, shown to the planner when ok is false."
    )


class SingleSiteResult(ContractModel):
    """The engine's result for this site on its own. Combined effects always come from rescore."""

    acs_gain: float
    drivers: list[DriverTag]
    ventilation: VentilationCheck


class Site(ContractModel):
    """A candidate site for one intervention type."""

    id: str
    type: InterventionType
    name: str
    geometry: SiteGeometry
    points: list[LonLat] | None = Field(default=None, description="Tree positions, for tree rows only.")
    quantity: float = Field(description="Units at this site (trees, or m²), in the unit of the type's UnitCost.")
    time_to_benefit: TimeToBenefit
    wait_point: str | None = Field(default=None, description="The waiting point this site serves, if any.")
    hw: float | None = Field(default=None, description="Street height-to-width ratio, for tree rows.")
    single_site: SingleSiteResult


class InterventionChange(ContractModel):
    kind: InterventionType
    site_id: str
    quantity: float


class BuildingChange(ContractModel):
    kind: Literal["building"]
    site_id: str = Field(description="The parcel id the building goes on.")
    design: BuildingDesign


Change = Annotated[InterventionChange | BuildingChange, Field(discriminator="kind")]
"""One change to an area: an intervention on a site (Repair) or a building on a parcel (Protect)."""


class RescoreRequest(ContractModel):
    changes: list[Change]
    unit_costs: UnitCosts


class BlockResult(ContractModel):
    id: str
    before: Scores
    after: Scores


class AreaResult(ContractModel):
    """Result of rescore: the one scoring path for every change set."""

    before: AreaScores
    after: AreaScores
    blocks: list[BlockResult] = Field(description="Blocks whose scores changed.")
    segments: dict[str, ShadeByTime] = Field(description="Footpath chunks whose shade changed, with their new state.")
    ventilation_ok: bool
    worst_vci_drop: float
    wait_points_covered: int
    cost_inr: float
    quick_win_cost_inr: float = Field(description="Cost of interventions that help within weeks or one season.")
    drivers: list[DriverTag]
    blocks_worse: int = Field(description="Existing blocks whose cooling score falls.")
    risk: RiskInfo | None = Field(default=None, description="Protect: the worst risk across proposed buildings.")
    parcel_risk: dict[str, RiskInfo] | None = Field(default=None, description="Protect: risk per parcel.")


class RejectedOption(ContractModel):
    site_id: str
    driver: DriverTag
    reason: str
