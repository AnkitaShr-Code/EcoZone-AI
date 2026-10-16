"""Agent runs: search requests, scored candidates, results and the SSE event stream.

POST /api/areas/{area}/runs starts a run and returns StartRunResponse; GET /api/runs/{runId}/events
streams SearchEvent with `id:` = seq; DELETE /api/runs/{runId} stops it (api/RULES.md).
"""

from typing import Annotated, Literal

from pydantic import Field

from .area import UnitCosts
from .common import ContractModel, DriverTag, ErrorCode
from .protect import BuildingDesign, RiskInfo
from .repair import Change, RejectedOption


class RepairSearchRequest(ContractModel):
    mode: Literal["repair"]
    budget_inr: float = Field(gt=0)
    unit_costs: UnitCosts
    quick_win_share_pct: float = Field(ge=0, le=100, description="Share of the budget that must help this summer.")


class ProtectSearchRequest(ContractModel):
    mode: Literal["protect"]
    parcel_id: str
    proposal: BuildingDesign
    keep_floor_area_pct: float = Field(
        ge=0, le=100, description="Option B keeps at least this share of A's floor area."
    )
    min_floor_area_pct: float = Field(ge=0, le=100, description="Option C keeps at least this share.")


SearchRequest = Annotated[RepairSearchRequest | ProtectSearchRequest, Field(discriminator="mode")]


class StartRunResponse(ContractModel):
    run_id: str


class Candidate(ContractModel):
    """One option scored by the engine during a search."""

    id: str
    round: int
    source: Literal["gemini", "greedy", "proposal"]
    label: str
    changes: list[Change]
    score: float = Field(description="Repair: area cooling score after. Protect: worst change (lower is better).")
    cost_inr: float
    floor_area_pct: float | None = None
    risk: RiskInfo | None = Field(default=None, description="Protect: the engine's risk label for this design.")
    valid: bool
    invalid_reason: str | None = None


class DesignOption(ContractModel):
    key: Literal["A", "B", "C"]
    title: str
    candidate: Candidate
    design: BuildingDesign
    trade_off: str


class ExplainRequest(ContractModel):
    changes: list[Change]
    unit_costs: UnitCosts


class Explanation(ContractModel):
    """Written by the agent from engine values; every number appears in a tool result or planner input."""

    paragraphs: list[str]
    drivers: list[DriverTag]
    source: Literal["gemini", "template"] = Field(
        description="'template' when the output guard rejected the model twice and fell back."
    )


class SearchResult(ContractModel):
    best: Candidate
    gemini_beat_greedy: bool | None = Field(default=None, description="Repair: if false, best is the greedy plan.")
    options: list[DesignOption] | None = Field(default=None, description="Protect: options A, B and C.")
    rejected: list[RejectedOption]
    rounds: int
    explanation: Explanation


class BaselineEvent(ContractModel):
    type: Literal["baseline"]
    seq: int
    candidate: Candidate


class RoundEvent(ContractModel):
    type: Literal["round"]
    seq: int
    round: int


class CandidateEvent(ContractModel):
    type: Literal["candidate"]
    seq: int
    candidate: Candidate


class GuardEvent(ContractModel):
    """The output guard rejected model text; `fallback` is true when a template replaced it."""

    type: Literal["guard"]
    seq: int
    violations: list[str]
    fallback: bool


class ErrorEvent(ContractModel):
    """The run ended early; the best scored result so far follows in a done event when one exists."""

    type: Literal["error"]
    seq: int
    code: ErrorCode
    message: str


class DoneEvent(ContractModel):
    type: Literal["done"]
    seq: int
    result: SearchResult


SearchEvent = Annotated[
    BaselineEvent | RoundEvent | CandidateEvent | GuardEvent | ErrorEvent | DoneEvent, Field(discriminator="type")
]
