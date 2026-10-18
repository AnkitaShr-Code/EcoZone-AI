"""The API over the real engine and the tiny fixture bundle: every read route against its contract model."""

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

import ecozone_contract as c
from ecozone_agents import AgentSettings
from ecozone_api.main import create_app
from ecozone_api.settings import Settings

TINY = Path(__file__).resolve().parents[2] / "engine" / "tests" / "fixtures" / "tiny"
UNIT_COSTS = {
    kind: {"unit": unit, "inr": inr, "source": "test"}
    for kind, unit, inr in [
        ("tree_row", "tree", 9250),
        ("shade", "m²", 4900),
        ("depave", "m²", 910),
        ("pocket_green", "m²", 1350),
        ("cool_roof", "m²", 300),
    ]
}


def _no_constants(name: str) -> Any:
    raise ValueError(f"{name} in a response body")


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    root = tmp_path_factory.mktemp("bundles")
    shutil.copytree(TINY, root / "tiny")
    settings = Settings(bundle_uri=str(root), app_dist=root / "no-dist")
    no_llm = AgentSettings(_env_file=None, llm="gemini", google_cloud_project=None)  # pyright: ignore[reportCallIssue]
    with TestClient(create_app(settings, agent_settings=no_llm)) as test_client:
        yield test_client


def body_of(response: Any) -> Any:
    """The JSON body, refusing NaN and Infinity (which Python's json would accept)."""
    assert response.status_code == 200, response.text
    return json.loads(response.text, parse_constant=_no_constants)


def test_summary_is_a_contract_area_summary(client: TestClient) -> None:
    area = c.AreaSummary.model_validate(body_of(client.get("/api/areas/tiny")))
    assert area.mock is False
    assert area.city == "Test"
    assert area.shade_times == ["13:00", "15:00", "16:00"]
    assert area.counts.blocks == 6
    assert area.counts.segments == 123
    listed = body_of(client.get("/api/areas/tiny/sites"))
    assert area.counts.sites == sum(
        1 for s in listed if s["singleSite"]["ventilation"]["ok"]
    )  # rejected rows are listed, not counted
    assert area.data_gaps.buildings_by_height_source == {
        "osm_height": 1,
        "osm_levels": 8,
        "open_buildings": 0,
        "typology": 15,
    }
    west, south, east, north = area.bbox
    assert 73.8 < west < area.center[0] < east < 73.9
    assert 18.5 < south < area.center[1] < north < 18.6
    assert area.engine.wind_from_deg == 300.0
    assert 0 <= area.baseline.acs <= 100


@pytest.mark.parametrize(
    ("name", "model", "count"),
    [
        ("blocks", c.BlockLayer, 6),
        ("segments", c.SegmentLayer, 123),
        ("buildings", c.BuildingLayer, 24),
        ("waitPoints", c.WaitPointLayer, 3),
        ("parcels", c.ParcelLayer, 3),
    ],
)
def test_layers_validate_against_the_contract(
    client: TestClient, name: str, model: type[c.ContractModel], count: int
) -> None:
    layer = model.model_validate(body_of(client.get(f"/api/areas/tiny/layers/{name}")))
    assert len(layer.features) == count  # pyright: ignore[reportAttributeAccessIssue]


def test_sites_validate_and_list_rejected_tree_rows_with_a_reason(client: TestClient) -> None:
    sites = TypeAdapter(list[c.Site]).validate_python(body_of(client.get("/api/areas/tiny/sites")))
    assert sites
    assert len({s.id for s in sites}) == len(sites)
    tree_rows = [s for s in sites if s.type == "tree_row"]
    assert tree_rows
    for s in tree_rows:
        assert s.points and len(s.points) == round(s.quantity)
    offered = [s for s in tree_rows if s.single_site.ventilation.ok]
    rejected = [s for s in tree_rows if not s.single_site.ventilation.ok]
    assert offered and rejected
    assert all(s.hw is not None and s.hw < 1.0 for s in offered)
    assert all(s.hw is not None and s.hw >= 1.0 for s in rejected)
    for s in rejected:
        assert s.single_site.ventilation.driver == "CANOPY_OBSTRUCTION"
        assert s.single_site.ventilation.reason and "breeze" in s.single_site.ventilation.reason
        assert s.single_site.acs_gain == 0
    assert all(s.points is None for s in sites if s.type != "tree_row")
    only_shade = body_of(client.get("/api/areas/tiny/sites", params={"types": "shade"}))
    assert only_shade
    assert {s["type"] for s in only_shade} == {"shade"}


def test_hotspots_are_ranked_with_drivers(client: TestClient) -> None:
    hotspots = TypeAdapter(list[c.Hotspot]).validate_python(body_of(client.get("/api/areas/tiny/hotspots?top=3")))
    assert [h.rank for h in hotspots] == [1, 2, 3]
    assert hotspots[0].priority >= hotspots[1].priority >= hotspots[2].priority
    assert any(h.drivers for h in hotspots)


def test_rescore_and_greedy_run_on_the_real_engine(client: TestClient) -> None:
    sites = body_of(client.get("/api/areas/tiny/sites"))
    offered = [s for s in sites if s["singleSite"]["ventilation"]["ok"]]
    picked = [next(s for s in offered if s["type"] == kind) for kind in ("shade", "tree_row")]
    changes = [{"kind": s["type"], "siteId": s["id"], "quantity": s["quantity"]} for s in picked]
    result = c.AreaResult.model_validate(
        body_of(client.post("/api/areas/tiny/rescore", json={"changes": changes, "unitCosts": UNIT_COSTS}))
    )
    assert result.after.pss >= result.before.pss
    assert result.cost_inr > 0
    assert result.ventilation_ok

    request = {"mode": "repair", "budgetInr": 500_000, "unitCosts": UNIT_COSTS, "quickWinSharePct": 20}
    candidate = c.Candidate.model_validate(body_of(client.post("/api/areas/tiny/greedy", json=request)))
    assert candidate.source == "greedy"
    assert candidate.changes
    assert candidate.cost_inr <= 500_000


def test_rescore_refuses_a_rejected_tree_row(client: TestClient) -> None:
    response = client.post(
        "/api/areas/tiny/rescore",
        json={"changes": [{"kind": "tree_row", "siteId": "s_0001", "quantity": 2}], "unitCosts": UNIT_COSTS},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_CHANGE"
