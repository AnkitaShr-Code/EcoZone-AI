"""Agent runs inside this instance: an asyncio task per run and a full event log for replay (api/RULES.md).

The search itself lives in `agents` (WP7) behind the `SearchRunner` protocol, so this module only
sequences events, streams them, stops runs and stores the result.
"""

import asyncio
import contextlib
import logging
import uuid
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

import ecozone_engine as e
from ecozone_contract import Explanation, SearchRequest, SearchResult, UnitCosts
from ecozone_contract.repair import BuildingChange, InterventionChange
from ecozone_contract.runs import (
    BaselineEvent,
    CandidateEvent,
    DoneEvent,
    ErrorEvent,
    GuardEvent,
    RoundEvent,
)

from .errors import ApiError
from .store import RunRecord, Store

log = logging.getLogger(__name__)

Event = BaselineEvent | RoundEvent | CandidateEvent | GuardEvent | ErrorEvent | DoneEvent
Emit = Callable[[Event], None]
"""Appends one event; the manager overwrites `seq`, so runners pass seq=0."""

HEARTBEAT_S = 15.0


class SearchRunner(Protocol):
    """Implemented by `agents` (WP7). `search` emits events and ends with a done or error event."""

    async def search(self, area: e.AreaModel, request: SearchRequest, emit: Emit) -> None: ...

    async def explain(
        self, area: e.AreaModel, changes: Sequence[InterventionChange | BuildingChange], unit_costs: UnitCosts
    ) -> Explanation: ...


class UnavailableRunner:
    """Stands in until the agents package provides a runner (WP7)."""

    message = "AI search is not available yet (WP7, see docs/TASKS.md). The engine routes work without it."

    async def search(self, area: e.AreaModel, request: SearchRequest, emit: Emit) -> None:
        emit(ErrorEvent(type="error", seq=0, code="NOT_IMPLEMENTED", message=self.message))

    async def explain(
        self, area: e.AreaModel, changes: Sequence[InterventionChange | BuildingChange], unit_costs: UnitCosts
    ) -> Explanation:
        raise ApiError("NOT_IMPLEMENTED", self.message, 501)


@dataclass
class Run:
    id: str
    area_id: str
    request: SearchRequest
    events: list[Event] = field(default_factory=list[Event])
    finished: bool = False
    task: asyncio.Task[None] | None = None
    changed: asyncio.Condition = field(default_factory=asyncio.Condition)

    @property
    def result(self) -> SearchResult | None:
        return next((ev.result for ev in reversed(self.events) if isinstance(ev, DoneEvent)), None)


class RunManager:
    def __init__(self, runner: SearchRunner, store: Store) -> None:
        self.runner = runner
        self.store = store
        self._runs: dict[str, Run] = {}

    def start(self, area: e.AreaModel, request: SearchRequest) -> Run:
        run = Run(id=uuid.uuid4().hex[:12], area_id=area.area_id, request=request)
        self._runs[run.id] = run
        run.task = asyncio.create_task(self._execute(run, area), name=f"run-{run.id}")
        return run

    def get(self, run_id: str) -> Run:
        run = self._runs.get(run_id)
        if run is None:
            raise ApiError("RUN_NOT_FOUND", f"Run {run_id} is not on this server. Start the search again.", 404)
        return run

    async def stop(self, run_id: str) -> None:
        """Cancel the run; the runner keeps the best result so far by emitting done before it exits."""
        run = self.get(run_id)
        if run.task and not run.task.done():
            run.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await run.task

    async def events(self, run_id: str, after_seq: int = 0) -> AsyncIterator[Event | None]:
        """Events with seq > after_seq, then new ones as they arrive; None is a heartbeat."""
        run = self.get(run_id)
        sent = after_seq
        while True:
            async with run.changed:
                if len(run.events) <= sent and not run.finished:
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(run.changed.wait(), HEARTBEAT_S)
                pending = run.events[sent:]
                finished = run.finished
            if not pending and not finished:
                yield None
            for event in pending:
                yield event
            sent += len(pending)
            if finished and sent >= len(run.events):
                return

    async def _execute(self, run: Run, area: e.AreaModel) -> None:
        def emit(event: Event) -> None:
            run.events.append(event.model_copy(update={"seq": len(run.events) + 1}))
            asyncio.get_running_loop().create_task(self._notify(run))

        try:
            await self.runner.search(area, run.request, emit)
        except asyncio.CancelledError:
            log.info("Run %s stopped", run.id)
        except Exception:
            log.exception("Run %s failed", run.id)
            emit(ErrorEvent(type="error", seq=0, code="INTERNAL", message="The search failed. Try again."))
        finally:
            run.finished = True
            await self._notify(run)
            self._save(run)

    async def _notify(self, run: Run) -> None:
        async with run.changed:
            run.changed.notify_all()

    def _save(self, run: Run) -> None:
        record = RunRecord(
            run_id=run.id, area_id=run.area_id, request=run.request, result=run.result, finished_at=datetime.now(UTC)
        )
        try:
            self.store.save_run(record)
        except Exception:
            log.exception("Could not save run %s", run.id)
