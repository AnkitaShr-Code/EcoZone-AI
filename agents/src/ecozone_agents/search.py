"""The one search loop: Proposer (model) → Scorer (code, engine) → Judge (code), for Repair and Protect.

Mode-specific behaviour (candidate shape, validity rules, threshold, prompt, result) lives in a
`SearchMode` passed in, never in a second loop (agents/RULES.md "One search loop"). docs/DESIGN.md
C4 describes the same three steps as an ADK LoopAgent; the choice to write them as plain asyncio is
recorded in ENGINEERING_RULES.md §2.

Event order, matching the UI's mock (app/src/api/mock/searchMock.ts): `baseline`, then per round a
`round` event and one `candidate` event per scored candidate, then `done`.
"""

import asyncio
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

import ecozone_contract as c
import ecozone_engine as e
from ecozone_contract.runs import BaselineEvent, CandidateEvent, ErrorEvent, RoundEvent

from .config import AgentSettings
from .errors import ModelError
from .ports import Emit, Proposal, ProposalRequest, Proposer

log = logging.getLogger(__name__)

NEG_INF = float("-inf")


@dataclass(frozen=True)
class Scored:
    """A candidate with the engine result behind it. `value` is what the mode compares (Repair: ACS after,
    higher is better; Protect: worst change, lower is better); the contract `Candidate` carries rounded values."""

    candidate: c.Candidate
    value: float
    changes: tuple[e.Change, ...] = ()
    result: e.AreaResultData | None = None
    design: c.BuildingDesign | None = None

    @property
    def valid(self) -> bool:
        return self.candidate.valid


class SearchMode(Protocol):
    name: Literal["repair", "protect"]

    async def baseline(self) -> Scored:
        """Round 0: the greedy plan (Repair) or the proposal as entered (Protect)."""
        ...

    def brief(self, scored: Sequence[Scored], round_no: int) -> dict[str, object]:
        """The compact JSON-able summary the proposer sees: ids, costs, single-site gains, best so far."""
        ...

    async def score(self, proposal: Proposal, round_no: int, ordinal: int) -> Scored | None:
        """Score one proposal with the engine, or return None when it repeats an earlier candidate."""
        ...

    def objectives(self, scored: Sequence[Scored]) -> tuple[float, ...]:
        """Higher is better in every slot; -inf when nothing valid exists yet."""
        ...


@dataclass(frozen=True)
class Judge:
    """Decides when to stop (docs/PLANNING.md): at the round limit, or when no gain beats the threshold."""

    max_rounds: int
    min_rounds: int
    threshold: float

    def stop(self, round_no: int, before: tuple[float, ...], after: tuple[float, ...]) -> bool:
        if round_no >= self.max_rounds:
            return True
        if round_no < self.min_rounds:
            return False
        return all(_gain(b, a) <= self.threshold for b, a in zip(before, after, strict=True))


def _gain(before: float, after: float) -> float:
    return 0.0 if before == after else after - before


@dataclass
class SearchLog:
    """What the loop produced so far; the runner turns it into the result, also after a stop."""

    scored: list[Scored] = field(default_factory=list[Scored])
    rounds: int = 0
    candidates: int = 0
    error: ErrorEvent | None = None


async def run_loop(
    mode: SearchMode, proposer: Proposer, emit: Emit, settings: AgentSettings, state: SearchLog, started: float
) -> None:
    """Run baseline and rounds, filling `state`. Cancellation propagates; `state` keeps the best so far."""
    baseline = await mode.baseline()
    state.scored.append(baseline)
    emit(BaselineEvent(type="baseline", seq=0, candidate=baseline.candidate))

    judge = Judge(
        settings.max_rounds,
        settings.min_rounds,
        settings.repair_threshold if mode.name == "repair" else settings.protect_threshold,
    )

    def remaining() -> float:
        return settings.search_time_limit_s - (time.monotonic() - started)

    for round_no in range(1, settings.max_rounds + 1):
        if remaining() <= 0:
            log.info("Search time limit reached; returning the best so far")
            return
        emit(RoundEvent(type="round", seq=0, round=round_no))
        before = mode.objectives(state.scored)
        request = ProposalRequest(
            mode=mode.name,
            round=round_no,
            count=settings.proposals_per_round,
            brief=mode.brief(state.scored, round_no),
        )
        try:
            async with asyncio.timeout(min(settings.proposer_timeout_s, max(remaining(), 0.001))):
                proposals = await proposer.propose(request)
        except (ModelError, TimeoutError) as exc:
            log.warning("Proposer failed in round %d: %s", round_no, exc)
            state.error = ErrorEvent(
                type="error",
                seq=0,
                code="INTERNAL",
                message="The AI proposer did not answer in time. The best result found so far is shown.",
            )
            emit(state.error)
            return
        state.rounds = round_no
        for proposal in proposals[: settings.proposals_per_round]:
            if remaining() <= 0:
                return
            scored = await mode.score(proposal, round_no, state.candidates + 1)
            if scored is None:
                continue
            state.candidates += 1
            state.scored.append(scored)
            emit(CandidateEvent(type="candidate", seq=0, candidate=scored.candidate))
        if judge.stop(round_no, before, mode.objectives(state.scored)):
            return
