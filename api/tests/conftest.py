"""Fixtures: a tiny engine that satisfies `EnginePort` with fixed values, so routes test without WP5,
and a scripted search runner standing in for the agents (WP7)."""

import asyncio
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString, Point, Polygon, box

import ecozone_contract as c
import ecozone_engine as e
from ecozone_api.main import create_app
from ecozone_api.run_manager import Emit
from ecozone_api.settings import Settings
from ecozone_api.store import MemoryStore
from ecozone_contract.runs import CandidateEvent, DoneEvent, RoundEvent

X0, Y0 = 374_000.0, 2_047_500.0  # EPSG:32643, Deccan Gymkhana, Pune
SCORES = e.Scores(vci=61.04, hei=58.26, gcs=22.0, pss=31.55)
AREA = e.AreaScores(vci=61.04, hei=58.26, gcs=22.0, pss=31.55, acs=44.44)
SITES = {"s_tree_1": ("tree_row", 12.0, 4, 20), "s_shade_1": ("shade", 48.0, 10, 120)}


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def load_bundle(self, path: Path) -> e.AreaModel:
        return e.AreaModel(area_id=path.name, bundle_version="v1-test")

    def summary(self, area: e.AreaModel) -> e.AreaSummaryData:
        return e.AreaSummaryData(
            area_id=area.area_id,
            name="Deccan Gymkhana",
            city="Pune",
            bundle_version=area.bundle_version,
            bbox_xy=(X0, Y0, X0 + 800, Y0 + 600),
            reference_date="2026-05-15",
            shade_times=("13:00", "15:00", "16:00"),
            baseline=AREA,
            wind_from_deg=270.0,
            metres_per_floor=3.2,
            counts={"blocks": 1, "buildings": 1, "segments": 1, "wait_points": 1, "sites": 2, "parcels": 1},
            buildings_by_height_source={"osm_levels": 1, "typology": 0},
            derived_footpath_chunks=1,
            attribution="© OpenStreetMap contributors (ODbL)",
        )

    def layer(self, area: e.AreaModel, name: e.LayerName) -> list[e.Feature]:
        self.calls.append(f"layer:{name}")
        block = box(X0, Y0, X0 + 100, Y0 + 80)
        features = {
            "blocks": [
                e.Feature(
                    "blk_1",
                    block,
                    {
                        "area_m2": 8000.0,
                        "scores": SCORES,
                        "priority": 72.345,
                        "priority_class": "high",
                        "built_form": "dense_low_rise",
                        "wait_weight": 1.5,
                        "drivers": ("LOW_SHADE", "WAIT_POINTS"),
                    },
                )
            ],
            "segments": [
                e.Feature(
                    "ch_1",
                    LineString([(X0, Y0 - 3), (X0 + 10, Y0 - 3)]),
                    {
                        "road_name": "FC Road",
                        "road_class": "secondary",
                        "length_m": 10.0,
                        "block_id": "blk_1",
                        "near_wait": True,
                        "shaded": (False, True, True),
                    },
                )
            ],
            "buildings": [
                e.Feature(
                    "b_1", box(X0 + 5, Y0 + 5, X0 + 25, Y0 + 20), {"height_m": 9.6, "height_source": "osm_levels"}
                )
            ],
            "wait_points": [
                e.Feature("wp_1", Point(X0 + 50, Y0 - 5), {"kind": "bus_stop", "name": "Deccan", "weight": 1.0})
            ],
            "parcels": [
                e.Feature(
                    "pc_1",
                    box(X0 + 60, Y0 + 40, X0 + 90, Y0 + 70),
                    {
                        "block_id": "blk_1",
                        "name": "Plot near FC Road",
                        "area_m2": 900.0,
                        "road_name": "FC Road",
                        "road_width_m": 18.0,
                        "street_bearing_deg": 12.0,
                        "neighbour_height_m": 12.0,
                    },
                )
            ],
            "sites": [
                e.Feature(
                    "s_tree_1",
                    LineString([(X0, Y0 - 6), (X0 + 60, Y0 - 6)]),
                    {
                        "kind": "tree_row",
                        "name": "FC Road east footpath",
                        "quantity": 12.0,
                        "time_to_benefit": "years",
                        "wait_point_id": "wp_1",
                        "h_w": 0.45,
                        "points": ((X0, Y0 - 6), (X0 + 5, Y0 - 6)),
                    },
                ),
                e.Feature(
                    "s_shade_1",
                    box(X0 + 45, Y0 - 9, X0 + 55, Y0 - 4),
                    {"kind": "shade", "name": "Deccan bus stop", "quantity": 48.0, "time_to_benefit": "weeks"},
                ),
            ],
        }
        return features[name]

    def hotspots(self, area: e.AreaModel, top: int) -> list[e.HotspotData]:
        return [e.HotspotData(1, "blk_1", 72.345, "high", SCORES, ("LOW_SHADE",), (X0 + 50, Y0 + 40))][:top]

    def single_site(self, area: e.AreaModel, site_id: str, unit_costs: e.UnitCosts) -> e.SingleSiteData:
        self.calls.append(f"single_site:{site_id}")
        return e.SingleSiteData(site_id, acs_gain=0.84, cost_inr=0.0, drivers=("SHADE_GAIN",), ventilation_ok=True)

    def rescore(self, area: e.AreaModel, changes: Sequence[e.Change], unit_costs: e.UnitCosts) -> e.AreaResultData:
        cost = 0.0
        for change in changes:
            if change.kind == "building":
                if change.site_id != "pc_1":
                    raise e.UnknownParcelError(change.site_id)
                continue
            if change.site_id not in SITES:
                raise e.UnknownSiteError(change.site_id)
            _, _, low, high = SITES[change.site_id]
            if not low <= change.quantity <= high:
                raise e.QuantityOutOfRangeError(change.site_id, change.quantity, low, high)
            cost += change.quantity * unit_costs[change.kind].inr  # pyright: ignore[reportArgumentType]
        after = e.AreaScores(vci=61.04, hei=57.0, gcs=22.5, pss=35.0, acs=45.123)
        risk = e.RiskInfo("MODERATE", "vci", -4.26) if any(c.kind == "building" for c in changes) else None
        return e.AreaResultData(
            before=AREA,
            after=after,
            blocks=(e.BlockResult("blk_1", SCORES, SCORES),),
            chunks=(("ch_1", (True, True, True)),),
            ventilation_ok=True,
            worst_vci_drop=0.0,
            wait_points_covered=1,
            cost_inr=cost + 0.4,
            quick_win_cost_inr=cost,
            drivers=("SHADE_GAIN",),
            blocks_worse=0,
            risk=risk,
            parcel_risk=(("pc_1", risk),) if risk else (),
        )

    def greedy_baseline(
        self, area: e.AreaModel, budget_inr: float, unit_costs: e.UnitCosts, quick_win_share_pct: float
    ) -> e.PortfolioData:
        changes = (e.Change("shade", "s_shade_1", 48.0),)
        return e.PortfolioData(changes, self.rescore(area, changes, unit_costs))

    def shadows(self, area: e.AreaModel, time: e.ShadeTime, changes: Sequence[e.Change] = ()) -> list[Polygon]:
        self.calls.append(f"shadows:{time}:{len(changes)}")
        return [box(X0 + 5, Y0 + 20, X0 + 25, Y0 + 30)]


CANDIDATE = c.Candidate(
    id="g1",
    round=1,
    source="gemini",
    label="Shade at the bus stop",
    changes=[c.InterventionChange(kind="shade", site_id="s_shade_1", quantity=48)],
    score=45.1,
    cost_inr=235_200,
    valid=True,
)
EXPLANATION = c.Explanation(
    paragraphs=["Shade at the bus stop covers one waiting point."], drivers=[], source="template"
)


class ScriptedRunner:
    """Emits two rounds then a result; with `hold`, waits after round 1 until stopped."""

    def __init__(self, hold: bool = False) -> None:
        self.hold = hold

    async def search(self, area: e.AreaModel, request: c.SearchRequest, emit: Emit) -> None:
        emit(RoundEvent(type="round", seq=0, round=1))
        emit(CandidateEvent(type="candidate", seq=0, candidate=CANDIDATE))
        try:
            if self.hold:
                await asyncio.sleep(60)
            emit(RoundEvent(type="round", seq=0, round=2))
        finally:
            result = c.SearchResult(
                best=CANDIDATE, gemini_beat_greedy=True, rejected=[], rounds=2, explanation=EXPLANATION
            )
            emit(DoneEvent(type="done", seq=0, result=result))

    async def explain(self, area: e.AreaModel, changes: Sequence[object], unit_costs: c.UnitCosts) -> c.Explanation:
        return EXPLANATION


@pytest.fixture
def engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


class ClientFactory:
    """Builds a client over the fake engine with one `deccan` bundle directory."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path

    def __call__(self, engine: object, *, hold: bool | None = None, store: MemoryStore | None = None) -> TestClient:
        (self.tmp_path / "bundles" / "deccan").mkdir(parents=True, exist_ok=True)
        settings = Settings(bundle_uri=str(self.tmp_path / "bundles"), app_dist=self.tmp_path / "no-dist")
        runner = None if hold is None else ScriptedRunner(hold=hold)
        return TestClient(create_app(settings, engine=engine, runner=runner, store=store))  # pyright: ignore[reportArgumentType]


@pytest.fixture
def make_client(tmp_path: Path) -> ClientFactory:
    return ClientFactory(tmp_path)


@pytest.fixture
def client(make_client: ClientFactory, engine: FakeEngine, store: MemoryStore) -> Iterator[TestClient]:
    with make_client(engine, hold=False, store=store) as test_client:
        yield test_client
