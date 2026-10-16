"""Shared closed sets, the base model config and the error shape (contract/RULES.md)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ContractModel(BaseModel):
    """Base for every wire model: frozen, no extra fields, snake_case in Python, camelCase on the wire."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


Mode = Literal["repair", "protect"]
ShadeTime = Literal["13:00", "15:00", "16:00"]
InterventionType = Literal["tree_row", "shade", "depave", "pocket_green", "cool_roof"]
IndexKey = Literal["vci", "hei", "gcs", "pss"]
PriorityClass = Literal["high", "medium", "low"]
TimeToBenefit = Literal["weeks", "season", "years"]
RiskLabel = Literal["LOW", "MODERATE", "HIGH"]
HeightSource = Literal["osm_height", "osm_levels", "open_buildings", "typology"]
"""Where a building height came from (pipeline/RULES.md, height fallback chain). The UI labels `typology` Default."""
BuiltForm = Literal["dense_low_rise", "other"]
WaitPointKind = Literal["school", "college", "hospital", "clinic", "marketplace", "bus_stop"]
LayerName = Literal["blocks", "segments", "buildings", "waitPoints", "parcels"]
ShadeByTime = tuple[bool, bool, bool]
"""Shade state per reference time, in the order of `AreaSummary.shade_times`."""
LonLat = tuple[float, float]
"""WGS84 longitude, latitude, rounded to 6 decimals by the API."""

DriverTag = Literal[
    # Repair priority drivers (why a block ranks high)
    "IMPERVIOUS_HIGH",
    "LOW_SHADE",
    "WAIT_POINTS",
    "DENSE_LOW_RISE",
    "LOW_GREEN",
    # Repair intervention drivers
    "SHADE_GAIN",
    "GREEN_LINK",
    "IMPERVIOUS_LOSS",
    "ALBEDO_GAIN",
    "WAIT_POINT_COVERED",
    "CANOPY_OBSTRUCTION",
    # Protect building drivers
    "OBSTRUCTION",
    "ORIENTATION",
    "BUILT_RUN",
    "IMPERVIOUS_GAIN",
    "MASS_GAIN",
    "GREEN_LOSS",
    "GREEN_ISOLATED",
    "SHADE_LOSS",
]
"""Engine driver tags (docs/PLANNING.md, grounding rules). Agents may only name drivers the engine returned."""

ErrorCode = Literal[
    "AREA_NOT_FOUND",
    "SITE_NOT_FOUND",
    "PARCEL_NOT_FOUND",
    "RUN_NOT_FOUND",
    "QUANTITY_OUT_OF_RANGE",
    "INVALID_CHANGE",
    "NOT_IMPLEMENTED",
    "INTERNAL",
]


class ErrorDetail(ContractModel):
    code: ErrorCode
    message: str = Field(description="Says what happened and what to do; shown to the planner.")


class ErrorBody(ContractModel):
    """The one error shape for every route (ENGINEERING_RULES.md §6)."""

    error: ErrorDetail
