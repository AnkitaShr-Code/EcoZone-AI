"""Protect: a proposed building envelope and its risk label."""

from pydantic import Field

from .common import ContractModel, IndexKey, RiskLabel


class BuildingDesign(ContractModel):
    """A proposed building envelope. Floor area proxy = footprint % × floors."""

    floors: int = Field(ge=1)
    footprint_pct: float = Field(ge=0, le=100)
    green_pct: float = Field(ge=0, le=100)
    orientation_deg: float = Field(ge=0, lt=180, description="Bearing of the long side, degrees from north.")


class RiskInfo(ContractModel):
    """Worst change on a parcel's block: the largest of VCI drop, HEI rise, GCS drop, PSS drop."""

    label: RiskLabel
    index: IndexKey
    change: float
