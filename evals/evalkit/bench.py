"""The session workbench: the loaded area, unit costs, cached heavy results and the search driver."""

import asyncio
import dataclasses
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import ecozone_contract as c
import ecozone_engine as e
from ecozone_agents import AgentSettings, build_runner
from ecozone_contract.runs import DoneEvent, ProtectSearchRequest, RepairSearchRequest

from .adapter import CostsKey, EvalEngine, costs_key
from .bundle import BundleInfo
from .cases import AreaCases, Design, ProtectCase, RepairCase, unit_cost_rows

CostRows = dict[str, tuple[str, float, str]]
"""kind -> (unit, inr, source)"""


def to_costs(rows: CostRows) -> e.UnitCosts:
    return {kind: e.UnitCost(unit=u, inr=inr, source=src) for kind, (u, inr, src) in rows.items()}  # pyright: ignore[reportReturnType]


KINDS: tuple[e.InterventionKind, ...] = ("tree_row", "shade", "depave", "pocket_green", "cool_roof")


def canon(obj: object) -> str:
    """Canonical JSON of an engine result: the byte-equality the determinism evals compare."""
    return json.dumps(dataclasses.asdict(obj), sort_keys=True)  # pyright: ignore[reportArgumentType]


@dataclass(frozen=True)
class GreedyRun:
    portfolio: e.PortfolioData
    seconds: float


@dataclass
class SearchRun:
    events: list[str]
    done: DoneEvent
    seconds: float
    engine: EvalEngine

    @property
    def result(self) -> c.SearchResult:
        return self.done.result


@dataclass
class Bench:
    info: BundleInfo
    cases: AreaCases
    area: e.AreaModel
    load_seconds: float
    rows: CostRows
    costs: e.UnitCosts
    contract_costs: c.UnitCosts
    greedy: dict[str, GreedyRun] = field(default_factory=dict[str, GreedyRun])
    greedy_repeat: GreedyRun | None = None
    greedy_cache: dict[tuple[float, float, CostsKey], e.PortfolioData] = field(
        default_factory=dict[tuple[float, float, CostsKey], e.PortfolioData]
    )
    single_cache: dict[tuple[str, CostsKey], e.SingleSiteData] = field(
        default_factory=dict[tuple[str, CostsKey], e.SingleSiteData]
    )
    precompute_seconds: float = 0.0
    _precomputed: bool = False
    _searches: dict[tuple[str, int], SearchRun] = field(default_factory=dict[tuple[str, int], SearchRun])
    _rescored: dict[str, e.AreaResultData] = field(default_factory=dict[str, e.AreaResultData])

    @classmethod
    def create(cls, info: BundleInfo, cases: AreaCases) -> "Bench":
        t0 = time.perf_counter()
        area = e.load_bundle(info.path)
        load_seconds = time.perf_counter() - t0
        raw = unit_cost_rows()
        rows: CostRows = {k: (str(v["unit"]), float(v["inr"]), str(v["source"])) for k, v in raw.items()}
        contract_costs = c.UnitCosts.model_validate(
            {k: {"unit": u, "inr": inr, "source": src} for k, (u, inr, src) in rows.items()}
        )
        return cls(info, cases, area, load_seconds, rows, to_costs(rows), contract_costs)

    # ---------- sites, changes and cached single rescores ----------

    def site_quantities(self, site_id: str) -> tuple[float, float]:
        s = next(s for s in self.area.sites if s.site_id == site_id)
        return s.quantity_min, s.quantity_max

    def site_kind(self, site_id: str) -> e.InterventionKind:
        return next(s for s in self.area.sites if s.site_id == site_id).kind  # pyright: ignore[reportReturnType]

    def change(self, site_id: str, quantity: float | None = None) -> e.Change:
        qmin, _ = self.site_quantities(site_id)
        return e.Change(kind=self.site_kind(site_id), site_id=site_id, quantity=qmin if quantity is None else quantity)

    def rescore(self, changes: Sequence[e.Change]) -> e.AreaResultData:
        """`rescore` memoised for the checks that only read results (direction, range, cost). Determinism and speed
        call the engine directly."""
        key = repr(sorted((ch.kind, ch.site_id, ch.quantity, ch.params) for ch in changes))
        if key not in self._rescored:
            self._rescored[key] = e.rescore(self.area, changes, self.costs)
        return self._rescored[key]

    # ---------- slow engine results, computed once across processes ----------

    def ensure_precomputed(self) -> None:
        """Greedy for every Repair case (and the determinism case a second time) and every offered site on its own,
        in this process, one after the other, so the timings are of an otherwise idle process."""
        if self._precomputed:
            return
        t0 = time.perf_counter()
        key = costs_key(self.costs)
        for rc in self.cases.repair:
            self.greedy[rc.id] = self._greedy_run(rc)
            self.greedy_cache[(rc.budget_inr, rc.quick_win_share_pct, key)] = self.greedy[rc.id].portfolio
        self.greedy_repeat = self._greedy_run(self.cases.repair_case(self.cases.determinism_case))
        for s in sorted(self.area.sites, key=lambda s: s.site_id):
            if s.rejected:
                continue
            single = e.single_site(self.area, s.site_id, self.costs)
            self.single_cache[(s.site_id, key)] = single
        self.precompute_seconds = time.perf_counter() - t0
        self._precomputed = True

    def _greedy_run(self, rc: RepairCase) -> GreedyRun:
        t0 = time.perf_counter()
        portfolio = e.greedy_baseline(self.area, rc.budget_inr, self.costs, rc.quick_win_share_pct)
        return GreedyRun(portfolio, time.perf_counter() - t0)

    def greedy_for(self, case: RepairCase) -> GreedyRun:
        self.ensure_precomputed()
        return self.greedy[case.id]

    # ---------- the search loop with the offline (fake) proposer ----------

    def new_engine(self) -> EvalEngine:
        self.ensure_precomputed()
        return EvalEngine(self.info, self.greedy_cache, self.single_cache)

    def _drive(
        self, request: RepairSearchRequest | ProtectSearchRequest, settings: AgentSettings | None = None
    ) -> SearchRun:
        engine = self.new_engine()
        # A long time limit so a slow machine cannot cut a run short and make two runs differ.
        settings = settings or AgentSettings(_env_file=None, llm="fake", search_time_limit_s=3600.0)  # pyright: ignore[reportCallIssue]
        runner = build_runner(engine, self.contract_costs, settings)
        assert runner is not None
        events: list[str] = []
        done: list[DoneEvent] = []

        def emit(event: Any) -> None:
            events.append(event.model_dump_json())
            if isinstance(event, DoneEvent):
                done.append(event)

        t0 = time.perf_counter()
        asyncio.run(runner.search(self.area, request, emit))
        seconds = time.perf_counter() - t0
        assert len(done) == 1, "the search ended without a result"
        return SearchRun(events, done[0], seconds, engine)

    def repair_request(self, case: RepairCase) -> RepairSearchRequest:
        return RepairSearchRequest(
            mode="repair",
            budget_inr=case.budget_inr,
            unit_costs=self.contract_costs,
            quick_win_share_pct=case.quick_win_share_pct,
        )

    def protect_request(self, case: ProtectCase) -> ProtectSearchRequest:
        return ProtectSearchRequest(
            mode="protect",
            parcel_id=case.parcel_id,
            proposal=design_to_contract(case.proposal),
            keep_floor_area_pct=case.keep_floor_area_pct,
            min_floor_area_pct=case.min_floor_area_pct,
        )

    def repair_search(self, case: RepairCase, run: int = 1) -> SearchRun:
        key = (f"repair:{case.id}", run)
        if key not in self._searches:
            self._searches[key] = self._drive(self.repair_request(case))
        return self._searches[key]

    def protect_search(self, case: ProtectCase, run: int = 1) -> SearchRun:
        key = (f"protect:{case.id}", run)
        if key not in self._searches:
            self._searches[key] = self._drive(self.protect_request(case))
        return self._searches[key]


def design_to_contract(d: Design) -> c.BuildingDesign:
    return c.BuildingDesign(
        floors=d.floors, footprint_pct=d.footprint_pct, green_pct=d.green_pct, orientation_deg=d.orientation_deg
    )


def building_change(parcel_id: str, d: Design) -> e.Change:
    """Params sorted by name (engine/RULES.md, "Building changes")."""
    params = (
        ("floors", float(d.floors)),
        ("footprint_pct", d.footprint_pct),
        ("green_pct", d.green_pct),
        ("orientation_deg", d.orientation_deg),
    )
    return e.Change(kind="building", site_id=parcel_id, quantity=1.0, params=params)
