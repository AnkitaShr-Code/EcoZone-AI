"""Fixtures for the agents tests: a fake engine, a scripted proposer, settings and request builders.

Nothing here touches a network or the real engine (which is still stubs). The fake engine scores by
a small table so tests can predict every number: site gains add up, two sites in one `group` overlap
(the second adds 30%), and a building's worst change grows with floors and footprint and shrinks
with green share and with the long side turned to the wind (270°, so the axis is 90).
"""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest
from shapely.geometry import Point, box

import ecozone_contract as c
import ecozone_engine as e
from ecozone_agents import AgentSettings, AgentsRunner
from ecozone_agents.ports import Event, Proposal, ProposalRequest
from ecozone_contract.runs import ProtectSearchRequest, RepairSearchRequest

X0, Y0 = 374_000.0, 2_047_500.0
OVERLAP = 0.3
BASE_ACS = 40.0
BASE_PSS = 30.0
QUICK = ("weeks", "season")


@dataclass
class SiteSpec:
    kind: e.InterventionKind
    name: str
    quantity: float
    ttb: str
    gain: float
    qmin: float = 1.0
    qmax: float = 1000.0
    vent_ok: bool = True
    reason: str | None = None
    group: str | None = None
    wait: str | None = None


def default_sites() -> dict[str, SiteSpec]:
    return {
        "s_shade_1": SiteSpec("shade", "Deccan bus stop", 48, "weeks", 3.0, 10, 120, group="stop", wait="wp_1"),
        "s_shade_2": SiteSpec("shade", "College gate", 40, "weeks", 2.8, 10, 120, group="stop", wait="wp_2"),
        "s_tree_1": SiteSpec("tree_row", "FC Road east footpath", 12, "years", 1.5, 4, 20),
        "s_dep_1": SiteSpec("depave", "School yard", 300, "season", 2.0, 50, 600),
        "s_pg_1": SiteSpec("pocket_green", "Vacant plot", 150, "years", 1.8, 50, 400),
        "s_roof_1": SiteSpec("cool_roof", "Dense block roofs", 600, "weeks", 1.2, 100, 900),
        "s_tree_9": SiteSpec(
            "tree_row", "Narrow lane", 10, "years", 3.5, 4, 20, vent_ok=False, reason="Street is too deep and narrow: canopy would block the breeze."
        ),
    }


def risk_label(worst: float) -> e.RiskLabel:
    return "LOW" if worst < 10 else "MODERATE" if worst < 25 else "HIGH"


class FakeEngine:
    """Implements `EnginePort` with predictable numbers. `fail` maps a method name to an exception to raise."""

    def __init__(self, sites: dict[str, SiteSpec] | None = None, wind_from_deg: float = 270.0) -> None:
        self.sites = sites if sites is not None else default_sites()
        self.wind_from_deg = wind_from_deg
        self.fail: dict[str, Exception] = {}
        self.rescored: list[list[e.Change]] = []
        self.greedy_calls = 0
        self.single_site_calls = 0
        self.delay_s = 0.0

    def _maybe_fail(self, name: str) -> None:
        if name in self.fail:
            raise self.fail[name]

    def summary(self, area: e.AreaModel) -> e.AreaSummaryData:
        self._maybe_fail("summary")
        scores = e.AreaScores(vci=60, hei=60, gcs=20, pss=BASE_PSS, acs=BASE_ACS)
        return e.AreaSummaryData(
            area_id=area.area_id,
            name="Deccan Gymkhana",
            city="Pune",
            bundle_version=area.bundle_version,
            bbox_xy=(X0, Y0, X0 + 800, Y0 + 600),
            reference_date="2026-04-15",
            shade_times=("13:00", "15:00", "16:00"),
            baseline=scores,
            wind_from_deg=self.wind_from_deg,
            metres_per_floor=3.0,
        )

    def layer(self, area: e.AreaModel, name: e.LayerName) -> list[e.Feature]:
        self._maybe_fail("layer")
        if name == "parcels":
            props = {
                "block_id": "blk_1",
                "name": "Plot near FC Road",
                "area_m2": 900.0,
                "road_name": "FC Road",
                "road_width_m": 18.0,
                "street_bearing_deg": 12.0,
                "neighbour_height_m": 12.0,
            }
            return [e.Feature("pc_1", box(X0, Y0, X0 + 30, Y0 + 30), props)]
        if name == "sites":
            return [
                e.Feature(
                    sid,
                    Point(X0, Y0).buffer(5),
                    {
                        "kind": s.kind,
                        "name": s.name,
                        "quantity": s.quantity,
                        "time_to_benefit": s.ttb,
                        "wait_point_id": s.wait,
                    },
                )
                for sid, s in sorted(self.sites.items())
            ]
        return []

    def single_site(self, area: e.AreaModel, site_id: str, unit_costs: e.UnitCosts) -> e.SingleSiteData:
        self._maybe_fail("single_site")
        self.single_site_calls += 1
        s = self.sites[site_id]
        return e.SingleSiteData(
            site_id,
            acs_gain=s.gain,
            cost_inr=s.quantity * unit_costs[s.kind].inr,
            drivers=("SHADE_GAIN",) if s.kind == "shade" else ("GREEN_LINK",),
            ventilation_ok=s.vent_ok,
            ventilation_reason=s.reason,
        )

    def rescore(self, area: e.AreaModel, changes: Sequence[e.Change], unit_costs: e.UnitCosts) -> e.AreaResultData:
        self._maybe_fail("rescore")
        self.rescored.append(list(changes))
        building = [ch for ch in changes if ch.kind == "building"]
        if building:
            return self._building(building[0])
        gain = 0.0
        cost = quick = 0.0
        groups: set[str] = set()
        covered = 0
        kinds: list[str] = []
        for ch in changes:
            spec = self.sites.get(ch.site_id)
            if spec is None:
                raise e.UnknownSiteError(ch.site_id)
            if ch.kind != spec.kind or not spec.vent_ok:
                raise e.InvalidChangeError(f"Site {ch.site_id} cannot take a {ch.kind}.")
            if not spec.qmin <= ch.quantity <= spec.qmax:
                raise e.QuantityOutOfRangeError(ch.site_id, ch.quantity, spec.qmin, spec.qmax)
            share = spec.gain
            if spec.group and spec.group in groups:
                share *= OVERLAP
            if spec.group:
                groups.add(spec.group)
            gain += share
            line = ch.quantity * unit_costs[ch.kind].inr  # pyright: ignore[reportArgumentType]
            cost += line
            quick += line if spec.ttb in QUICK else 0.0
            covered += 1 if spec.wait else 0
            kinds.append(ch.kind)
        before = e.AreaScores(vci=60, hei=60, gcs=20, pss=BASE_PSS, acs=BASE_ACS)
        after = e.AreaScores(vci=60, hei=58, gcs=21, pss=BASE_PSS + gain, acs=BASE_ACS + gain)
        return e.AreaResultData(
            before=before,
            after=after,
            blocks=(),
            chunks=(),
            ventilation_ok=True,
            worst_vci_drop=0.0,
            wait_points_covered=covered,
            cost_inr=cost,
            quick_win_cost_inr=quick,
            drivers=("SHADE_GAIN",) if "shade" in kinds else ("GREEN_LINK",),
            blocks_worse=0,
        )

    def _building(self, ch: e.Change) -> e.AreaResultData:
        if ch.site_id != "pc_1":
            raise e.UnknownParcelError(ch.site_id)
        p = dict(ch.params)
        worst = p["floors"] * p["footprint_pct"] / 60 + (100 - p["green_pct"]) / 20 + abs(p["orientation_deg"] - 90) / 18
        scores = e.AreaScores(vci=60, hei=60, gcs=20, pss=BASE_PSS, acs=BASE_ACS)
        after = e.AreaScores(vci=60 - worst, hei=60, gcs=20, pss=BASE_PSS + 1.0, acs=BASE_ACS - worst / 4)
        return e.AreaResultData(
            before=scores,
            after=after,
            blocks=(),
            chunks=(),
            ventilation_ok=True,
            worst_vci_drop=worst,
            wait_points_covered=0,
            cost_inr=0.0,
            quick_win_cost_inr=0.0,
            drivers=("OBSTRUCTION", "SHADE_GAIN"),
            blocks_worse=2,
            risk=e.RiskInfo(risk_label(worst), "vci", worst),
            parcel_risk=(("pc_1", e.RiskInfo(risk_label(worst), "vci", worst)),),
        )

    def greedy_baseline(
        self, area: e.AreaModel, budget_inr: float, unit_costs: e.UnitCosts, quick_win_share_pct: float
    ) -> e.PortfolioData:
        """Quick wins by gain per rupee until the share is met, then the rest by gain per rupee (overlap ignored)."""
        self._maybe_fail("greedy_baseline")
        self.greedy_calls += 1
        usable = {sid: s for sid, s in self.sites.items() if s.vent_ok}

        def cost(sid: str) -> float:
            return usable[sid].quantity * unit_costs[usable[sid].kind].inr

        order = sorted(usable, key=lambda sid: (-usable[sid].gain / cost(sid), sid))
        target = budget_inr * quick_win_share_pct / 100
        picked: list[str] = []
        spent = quick = 0.0

        def add(sid: str) -> None:
            nonlocal spent, quick
            if sid in picked or spent + cost(sid) > budget_inr:
                return
            picked.append(sid)
            spent += cost(sid)
            quick += cost(sid) if usable[sid].ttb in QUICK else 0.0

        for sid in order:
            if quick >= target:
                break
            if usable[sid].ttb in QUICK:
                add(sid)
        for sid in order:
            add(sid)
        changes = tuple(e.Change(usable[sid].kind, sid, usable[sid].quantity) for sid in sorted(picked))
        return e.PortfolioData(changes, self.rescore(area, changes, unit_costs))


@dataclass
class ScriptedProposer:
    """Returns the queued proposals per round (the last list repeats) and records what it was shown."""

    rounds: Sequence[Sequence[Proposal]] = ()
    error: Exception | None = None
    delay_s: float = 0.0
    requests: list[ProposalRequest] = field(default_factory=list[ProposalRequest])

    async def propose(self, request: ProposalRequest) -> list[Proposal]:
        self.requests.append(request)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.error:
            raise self.error
        if not self.rounds:
            return []
        return list(self.rounds[min(len(self.requests) - 1, len(self.rounds) - 1)])


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings tests must not depend on the developer's shell or .env."""
    for name in (
        "ECOZONE_LLM",
        "GOOGLE_CLOUD_PROJECT",
        "ECOZONE_GEMINI_LOCATION",
        "ECOZONE_MODEL_PROPOSER",
        "ECOZONE_MODEL_WRITER",
    ):
        monkeypatch.delenv(name, raising=False)


def make_settings(**overrides: Any) -> AgentSettings:
    values: dict[str, Any] = {"llm": "fake", "google_cloud_project": None}
    values.update(overrides)
    return AgentSettings(_env_file=None, **values)  # pyright: ignore[reportCallIssue]


@pytest.fixture
def settings() -> Callable[..., AgentSettings]:
    return make_settings


@pytest.fixture
def engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
def area() -> e.AreaModel:
    return e.AreaModel(area_id="deccan", bundle_version="v1-test")


def _costs() -> c.UnitCosts:
    def row(unit: str, inr: float) -> c.UnitCost:
        return c.UnitCost(unit=unit, inr=inr, source="planner")

    return c.UnitCosts(
        tree_row=row("tree", 9250),
        shade=row("m²", 4900),
        depave=row("m²", 910),
        pocket_green=row("m²", 1350),
        cool_roof=row("m²", 300),
    )


@pytest.fixture
def unit_costs() -> c.UnitCosts:
    return _costs()


@pytest.fixture
def repair_request(unit_costs: c.UnitCosts) -> RepairSearchRequest:
    return RepairSearchRequest(mode="repair", budget_inr=700_000, unit_costs=unit_costs, quick_win_share_pct=20)


@pytest.fixture
def protect_request() -> ProtectSearchRequest:
    return ProtectSearchRequest(
        mode="protect",
        parcel_id="pc_1",
        proposal=c.BuildingDesign(floors=8, footprint_pct=60, green_pct=10, orientation_deg=0),
        keep_floor_area_pct=80,
        min_floor_area_pct=50,
    )


class Collector:
    """An `Emit` that keeps the events, as the run manager would."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def __call__(self, event: Event) -> None:
        self.events.append(event)

    def types(self) -> list[str]:
        return [ev.type for ev in self.events]

    def of(self, kind: type[Any]) -> list[Any]:
        return [ev for ev in self.events if isinstance(ev, kind)]

    @property
    def done(self) -> Any:
        return next(ev for ev in self.events if ev.type == "done").result


@pytest.fixture
def emit() -> Collector:
    return Collector()



@pytest.fixture
def make_runner(engine: FakeEngine, unit_costs: c.UnitCosts) -> Callable[..., AgentsRunner]:
    def build(proposer: Any, writer: Any = None, **settings: Any) -> AgentsRunner:
        return AgentsRunner(engine, proposer, writer, make_settings(**settings), unit_costs)

    return build

