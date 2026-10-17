"""A run through the real agents runner (offline rule proposer) over the fake engine, streamed as the app sees it."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import ecozone_contract as c
from ecozone_agents import AgentSettings
from ecozone_api.main import create_app
from ecozone_api.settings import Settings

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
REPAIR = {"mode": "repair", "budgetInr": 500_000, "unitCosts": UNIT_COSTS, "quickWinSharePct": 20}
PROTECT = {
    "mode": "protect",
    "parcelId": "pc_1",
    "proposal": {"floors": 6, "footprintPct": 60, "greenPct": 10, "orientationDeg": 0},
    "keepFloorAreaPct": 80,
    "minFloorAreaPct": 50,
}


def events(client: TestClient, run_id: str) -> list[dict[str, Any]]:
    body = client.get(f"/api/runs/{run_id}/events").text
    return [json.loads(line[len("data: ") :]) for line in body.splitlines() if line.startswith("data: ")]


@pytest.fixture
def fake_llm_client(tmp_path: Path, engine: Any) -> Iterator[TestClient]:
    (tmp_path / "bundles" / "deccan").mkdir(parents=True)
    settings = Settings(bundle_uri=str(tmp_path / "bundles"), app_dist=tmp_path / "no-dist")
    agents = AgentSettings(_env_file=None, llm="fake")  # pyright: ignore[reportCallIssue]
    with TestClient(create_app(settings, engine=engine, agent_settings=agents)) as client:  # pyright: ignore[reportArgumentType]
        yield client


def test_repair_run_streams_baseline_rounds_candidates_and_done(fake_llm_client: TestClient) -> None:
    run_id = fake_llm_client.post("/api/areas/deccan/runs", json=REPAIR).json()["runId"]
    got = events(fake_llm_client, run_id)
    types = [e["type"] for e in got]
    assert types[0] == "baseline" and types[-1] == "done"
    assert types[1] == "round" and "candidate" in types
    assert [e["seq"] for e in got] == list(range(1, len(got) + 1))
    assert got[0]["candidate"]["source"] == "greedy"
    result = c.SearchResult.model_validate(got[-1]["result"])
    assert result.best.cost_inr <= 500_000
    assert result.explanation.source == "template"
    assert result.rounds >= 1


def test_protect_run_returns_options_a_b_and_c(fake_llm_client: TestClient) -> None:
    run_id = fake_llm_client.post("/api/areas/deccan/runs", json=PROTECT).json()["runId"]
    got = events(fake_llm_client, run_id)
    assert got[0]["type"] == "baseline" and got[0]["candidate"]["source"] == "proposal"
    result = c.SearchResult.model_validate(got[-1]["result"])
    assert result.options is not None and [o.key for o in result.options] == ["A", "B", "C"]


def test_explain_route_uses_the_agents_runner(fake_llm_client: TestClient) -> None:
    body = {"changes": [{"kind": "shade", "siteId": "s_shade_1", "quantity": 48}], "unitCosts": UNIT_COSTS}
    explanation = c.Explanation.model_validate(fake_llm_client.post("/api/areas/deccan/explain", json=body).json())
    assert explanation.source == "template"
    assert "planner input" in " ".join(explanation.paragraphs)


def test_unknown_site_in_explain_keeps_the_error_shape(fake_llm_client: TestClient) -> None:
    body = {"changes": [{"kind": "shade", "siteId": "s_nope", "quantity": 1}], "unitCosts": UNIT_COSTS}
    response = fake_llm_client.post("/api/areas/deccan/explain", json=body)
    assert response.status_code == 404 and response.json()["error"]["code"] == "SITE_NOT_FOUND"


def test_gemini_without_settings_keeps_the_unavailable_runner(tmp_path: Path, engine: Any) -> None:
    (tmp_path / "bundles" / "deccan").mkdir(parents=True)
    settings = Settings(bundle_uri=str(tmp_path / "bundles"), app_dist=tmp_path / "no-dist")
    agents = AgentSettings(_env_file=None, llm="gemini", google_cloud_project=None)  # pyright: ignore[reportCallIssue]
    with TestClient(create_app(settings, engine=engine, agent_settings=agents)) as client:  # pyright: ignore[reportArgumentType]
        run_id = client.post("/api/areas/deccan/runs", json=REPAIR).json()["runId"]
        got = events(client, run_id)
    assert [(e["type"], e["code"]) for e in got] == [("error", "NOT_IMPLEMENTED")]
