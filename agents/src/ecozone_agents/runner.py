"""Entry points the API calls: `AgentsRunner.search` and `explain`, plus `build_runner` (agents/RULES.md).

Routing is code: the request's `mode` picks Repair or Protect, there is no LLM orchestrator. The class
satisfies api's `SearchRunner` protocol structurally (agents never import `ecozone_api`).

Failure behaviour (agents/RULES.md "Fail soft"): once the baseline exists, anything that goes wrong
ends the run with the best scored result so far, and a stop (task cancellation) emits `done` with
the best so far before the task exits.
"""

import asyncio
import logging
import time
from collections.abc import Sequence

import ecozone_contract as c
import ecozone_engine as e
from ecozone_contract.runs import DoneEvent, ErrorEvent, RepairSearchRequest

from . import to_contract as tc
from .catalog import SiteInfo, describe_sites, load_parcel, load_sites
from .config import AgentSettings
from .explain import write_explanation
from .facts import protect_facts, repair_facts
from .fake_llm import ScriptedModel  # noqa: F401  (re-exported for tests that build runners)
from .llm import GeminiClient, LlmProposer, LlmWriter
from .offline import RuleProposer
from .ports import Emit, EnginePort, Proposer, Writer
from .protect import ProtectMode
from .repair import RepairMode
from .search import SearchLog, SearchMode, run_loop

log = logging.getLogger(__name__)


class AgentsRunner:
    def __init__(
        self,
        engine: EnginePort,
        proposer: Proposer,
        writer: Writer | None,
        settings: AgentSettings,
        default_unit_costs: c.UnitCosts,
    ) -> None:
        self.engine = engine
        self.proposer = proposer
        self.writer = writer
        self.settings = settings
        self.default_unit_costs = default_unit_costs
        self._sites: dict[tuple[str, str, str], dict[str, SiteInfo]] = {}

    # ---------- search ----------

    async def search(self, area: e.AreaModel, request: c.SearchRequest, emit: Emit) -> None:
        started = time.monotonic()
        state = SearchLog()
        mode: SearchMode | None = None
        done = False

        async def finish(writer: Writer | None) -> None:
            nonlocal done
            assert mode is not None
            result = await mode.finish(state.scored, state.rounds, writer=writer, emit=emit)  # pyright: ignore[reportAttributeAccessIssue]
            emit(DoneEvent(type="done", seq=0, result=result))
            done = True

        try:
            mode = await self._make_mode(area, request)
            await run_loop(mode, self.proposer, emit, self.settings, state, started)
            await finish(self.writer)
        except asyncio.CancelledError:
            # Stopped by the planner: keep the best so far, with the template text so we exit quickly.
            if mode is not None and state.scored and not done:
                await finish(None)
            raise
        except Exception as exc:
            log.exception("Search failed")
            emit(_error_event(exc))
            if mode is not None and state.scored and not done:
                try:
                    await finish(None)
                except Exception:
                    log.exception("Could not build the best-so-far result")

    async def _make_mode(self, area: e.AreaModel, request: c.SearchRequest) -> SearchMode:
        reference_date, wind_from_deg = await self._area_facts(area)
        if isinstance(request, RepairSearchRequest):
            costs = tc.engine_unit_costs(request.unit_costs)
            sites = await self._catalog(area, request.unit_costs, costs)
            return RepairMode(
                engine=self.engine,
                area=area,
                request=request,
                sites=sites,
                settings=self.settings,
                reference_date=reference_date,
            )  # pyright: ignore[reportReturnType]
        parcel = await asyncio.to_thread(load_parcel, self.engine, area, request.parcel_id)
        return ProtectMode(
            engine=self.engine,
            area=area,
            request=request,
            unit_costs=self.default_unit_costs,
            parcel=parcel,
            settings=self.settings,
            wind_from_deg=wind_from_deg,
            reference_date=reference_date,
        )  # pyright: ignore[reportReturnType]

    async def _area_facts(self, area: e.AreaModel) -> tuple[str | None, float]:
        summary = await asyncio.to_thread(self.engine.summary, area)
        return summary.reference_date, summary.wind_from_deg

    async def _catalog(self, area: e.AreaModel, unit_costs: c.UnitCosts, costs: e.UnitCosts) -> dict[str, SiteInfo]:
        """Site list with single-site results, cached per bundle and unit costs (they depend on nothing else)."""
        key = (area.area_id, area.bundle_version, unit_costs.model_dump_json())
        if key not in self._sites:
            self._sites[key] = await asyncio.to_thread(load_sites, self.engine, area, costs)
        return self._sites[key]

    # ---------- explain ----------

    async def explain(
        self, area: e.AreaModel, changes: Sequence[c.InterventionChange | c.BuildingChange], unit_costs: c.UnitCosts
    ) -> c.Explanation:
        """Explain any change set from engine values; falls back to the template after 20 s or two guard rejections."""
        engine_changes = tc.engine_changes(changes)
        result = await asyncio.to_thread(self.engine.rescore, area, engine_changes, tc.engine_unit_costs(unit_costs))
        reference_date, _ = await self._area_facts(area)
        building = next((ch for ch in changes if isinstance(ch, c.BuildingChange)), None)
        if building is not None:
            parcel = await asyncio.to_thread(load_parcel, self.engine, area, building.site_id)
            facts = protect_facts(
                proposal=building.design,
                result=result,
                parcel=parcel,
                parcel_id=building.site_id,
                reference_date=reference_date,
            )
        else:
            sites = await asyncio.to_thread(describe_sites, self.engine, area)
            facts = repair_facts(
                result=result,
                changes=engine_changes,
                sites=sites,
                unit_costs=unit_costs,
                reference_date=reference_date,
            )
        return await write_explanation(self.writer, facts, self.settings)


def _error_event(exc: Exception) -> ErrorEvent:
    """Map an exception to the error event the UI shows (api/errors.py uses the same mapping for routes)."""
    if isinstance(exc, e.NotImplementedYetError):
        return ErrorEvent(type="error", seq=0, code="NOT_IMPLEMENTED", message=str(exc))
    if isinstance(exc, e.UnknownSiteError):
        return ErrorEvent(type="error", seq=0, code="SITE_NOT_FOUND", message=str(exc))
    if isinstance(exc, e.UnknownParcelError):
        return ErrorEvent(type="error", seq=0, code="PARCEL_NOT_FOUND", message=str(exc))
    if isinstance(exc, e.QuantityOutOfRangeError):
        return ErrorEvent(type="error", seq=0, code="QUANTITY_OUT_OF_RANGE", message=str(exc))
    if isinstance(exc, e.EngineInputError):
        return ErrorEvent(type="error", seq=0, code="INVALID_CHANGE", message=str(exc))
    return ErrorEvent(type="error", seq=0, code="INTERNAL", message="The search failed. Try again.")


def build_runner(
    engine: EnginePort, default_unit_costs: c.UnitCosts, settings: AgentSettings | None = None
) -> AgentsRunner | None:
    """The runner the settings ask for, or None when Gemini is selected but not configured.

    `ECOZONE_LLM=fake` gives the offline rule proposer and template text, with no cloud calls. Gemini
    needs `GOOGLE_CLOUD_PROJECT`, `ECOZONE_GEMINI_LOCATION` and both model ids; credentials are
    Application Default Credentials and are looked up only when the first model call is made.
    """
    settings = settings or AgentSettings()
    if settings.llm == "fake":
        log.warning("ECOZONE_LLM=fake: proposals come from offline rules and explanations from templates")
        return AgentsRunner(engine, RuleProposer(), None, settings, default_unit_costs)
    if not settings.gemini_configured:
        log.warning("Gemini is not configured (project, location and model ids); AI search is unavailable")
        return None
    client = GeminiClient(settings)
    return AgentsRunner(engine, LlmProposer(client), LlmWriter(client), settings, default_unit_costs)
