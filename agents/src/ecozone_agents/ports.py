"""Protocols the agents build against, so the engine and the model can both be faked in tests.

`EnginePort` is the slice of the engine's public API (engine/RULES.md) that agents call; the real
`ecozone_engine` module satisfies it, and so does api's wider `EnginePort`. `ModelClient` is the
only place a model is reached (the real one is `llm.GeminiClient`, the scripted one `fake_llm`).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

import ecozone_engine as e
from ecozone_contract.runs import (
    BaselineEvent,
    CandidateEvent,
    DoneEvent,
    ErrorEvent,
    GuardEvent,
    RoundEvent,
)

Event = BaselineEvent | RoundEvent | CandidateEvent | GuardEvent | ErrorEvent | DoneEvent
Emit = Callable[[Event], None]
"""Appends one event. Runners pass `seq=0`; the run manager numbers events (api/RULES.md)."""

Role = Literal["proposer", "writer"]
ModelOut = TypeVar("ModelOut", bound=BaseModel)


class EnginePort(Protocol):
    """Engine calls are sync and CPU-bound: agents run them through `asyncio.to_thread`."""

    def summary(self, area: e.AreaModel) -> e.AreaSummaryData: ...
    def layer(self, area: e.AreaModel, name: e.LayerName) -> list[e.Feature]: ...
    def single_site(self, area: e.AreaModel, site_id: str, unit_costs: e.UnitCosts) -> e.SingleSiteData: ...
    def rescore(self, area: e.AreaModel, changes: Sequence[e.Change], unit_costs: e.UnitCosts) -> e.AreaResultData: ...
    def greedy_baseline(
        self, area: e.AreaModel, budget_inr: float, unit_costs: e.UnitCosts, quick_win_share_pct: float
    ) -> e.PortfolioData: ...


class ModelClient(Protocol):
    """One structured call: system text + prompt in, a validated pydantic object out.

    Raises `errors.ModelError` for any failure (network, quota, timeout, answer not matching `schema`).
    """

    async def generate(self, *, role: Role, system: str, prompt: str, schema: type[ModelOut]) -> ModelOut: ...


@dataclass(frozen=True)
class RepairProposal:
    """One portfolio as the proposer returns it: site ids and optional quantities, never scores."""

    label: str
    changes: tuple[tuple[str, float | None], ...]
    """(site id, quantity). A missing quantity means the site's own quantity."""


@dataclass(frozen=True)
class DesignProposal:
    """One building design as the proposer returns it. Raw numbers: the scorer checks the ranges."""

    label: str
    floors: float
    footprint_pct: float
    green_pct: float
    orientation_deg: float


Proposal = RepairProposal | DesignProposal


@dataclass(frozen=True)
class ProposalRequest:
    """What the proposer sees: a compact JSON-able brief (ids, costs, single-site gains, best so far)."""

    mode: Literal["repair", "protect"]
    round: int
    count: int
    brief: dict[str, object]


class Proposer(Protocol):
    async def propose(self, request: ProposalRequest) -> list[Proposal]: ...


@dataclass(frozen=True)
class WriterOutput:
    paragraphs: list[str]
    drivers: list[str]


class Writer(Protocol):
    async def write(self, facts: dict[str, object], violations: Sequence[str] | None) -> WriterOutput:
        """Prose from engine facts. `violations` lists what the guard rejected in the previous attempt."""
        ...
