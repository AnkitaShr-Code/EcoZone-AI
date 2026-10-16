"""Routes against the fake engine: contract shapes, rounding, WGS84, caching, error codes, runs over SSE."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

import ecozone_contract as c
import ecozone_engine
from ecozone_api.store import MemoryStore
from ecozone_contract.runs import DoneEvent

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
DESIGN = {"floors": 6, "footprintPct": 60, "greenPct": 10, "orientationDeg": 90}


def sse(text: str) -> list[dict[str, Any]]:
    """Parse an SSE body into its data payloads, checking `id:` equals the event's seq."""
    events: list[dict[str, Any]] = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if not line.startswith(":"))
        if "data" in fields:
            data = json.loads(fields["data"])
            assert int(fields["id"]) == data["seq"]
            assert fields["event"] == data["type"]
            events.append(data)
    return events


# ---------- read routes ----------


def test_area_summary_is_a_contract_area_in_wgs84(client: TestClient) -> None:
    body = client.get("/api/areas/deccan").json()
    area = c.AreaSummary.model_validate(body)
    assert area.mock is False
    assert area.baseline.acs == 44.4
    west, south, east, north = area.bbox
    assert 73.7 < west < east < 73.9
    assert 18.4 < south < north < 18.6
    assert area.unit_cost_defaults.tree_row.inr == 9250
    assert area.unit_cost_defaults.tree_row.source_url is not None
    assert body["dataGaps"]["derivedFootpathSegments"] == 1


def test_unknown_area_is_area_not_found(client: TestClient) -> None:
    response = client.get("/api/areas/kothrud/hotspots")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AREA_NOT_FOUND"
    assert "deccan" in response.json()["error"]["message"]


@pytest.mark.parametrize(
    ("name", "model"),
    [
        ("blocks", c.BlockLayer),
        ("segments", c.SegmentLayer),
        ("buildings", c.BuildingLayer),
        ("waitPoints", c.WaitPointLayer),
        ("parcels", c.ParcelLayer),
    ],
)
def test_layers_validate_against_the_contract(client: TestClient, name: str, model: type[c.ContractModel]) -> None:
    response = client.get(f"/api/areas/deccan/layers/{name}")
    assert response.status_code == 200
    model.model_validate(response.json())


def test_layer_values_are_rounded_and_camel_cased(client: TestClient) -> None:
    block = client.get("/api/areas/deccan/layers/blocks").json()["features"][0]
    assert block["properties"]["priority"] == 72.3
    assert block["properties"]["scores"] == {"vci": 61.0, "hei": 58.3, "gcs": 22.0, "pss": 31.6}
    lon, lat = block["geometry"]["coordinates"][0][0]
    assert len(str(lon).split(".")[1]) <= 6
    assert 18.4 < lat < 18.6


def test_layers_are_cached_and_honour_etag(client: TestClient, engine: Any) -> None:
    first = client.get("/api/areas/deccan/layers/blocks")
    etag = first.headers["etag"]
    assert etag == '"v1-test"'
    again = client.get("/api/areas/deccan/layers/blocks", headers={"If-None-Match": etag})
    assert again.status_code == 304
    client.get("/api/areas/deccan/layers/blocks")
    assert engine.calls.count("layer:blocks") == 1


def test_unknown_layer_is_invalid_request(client: TestClient) -> None:
    response = client.get("/api/areas/deccan/layers/roads")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_shadows_today_and_with_changes(client: TestClient, engine: Any) -> None:
    today = client.get("/api/areas/deccan/shadows", params={"t": "15:00"})
    c.ShadowLayer.model_validate(today.json())
    changes = json.dumps([{"kind": "building", "siteId": "pc_1", "design": DESIGN}])
    with_changes = client.get("/api/areas/deccan/shadows", params={"t": "15:00", "changes": changes})
    assert with_changes.status_code == 200
    assert engine.calls == ["shadows:15:00:0", "shadows:15:00:1"]
    bad = client.get("/api/areas/deccan/shadows", params={"t": "15:00", "changes": "[{}]"})
    assert bad.json()["error"]["code"] == "INVALID_REQUEST"


def test_hotspots(client: TestClient) -> None:
    hotspots = TypeAdapter(list[c.Hotspot]).validate_python(client.get("/api/areas/deccan/hotspots?top=5").json())
    assert hotspots[0].block_id == "blk_1"
    assert hotspots[0].priority == 72.3


def test_sites_carry_single_site_results_and_filter_by_type(client: TestClient, engine: Any) -> None:
    sites = TypeAdapter(list[c.Site]).validate_python(client.get("/api/areas/deccan/sites").json())
    assert [s.id for s in sites] == ["s_tree_1", "s_shade_1"]
    tree = sites[0]
    assert tree.points is not None and len(tree.points) == 2
    assert tree.single_site.acs_gain == 0.8
    assert tree.hw == 0.45
    shade_only = client.get("/api/areas/deccan/sites?types=shade").json()
    assert [s["id"] for s in shade_only] == ["s_shade_1"]
    assert engine.calls.count("layer:sites") == 1


# ---------- rescore and greedy ----------


def test_rescore_returns_a_rounded_area_result(client: TestClient) -> None:
    body = {"changes": [{"kind": "shade", "siteId": "s_shade_1", "quantity": 48}], "unitCosts": UNIT_COSTS}
    result = c.AreaResult.model_validate(client.post("/api/areas/deccan/rescore", json=body).json())
    assert result.cost_inr == 235_200
    assert result.after.acs == 45.1
    assert result.segments == {"ch_1": (True, True, True)}
    assert result.risk is None


def test_rescore_building_change_returns_risk(client: TestClient) -> None:
    body = {"changes": [{"kind": "building", "siteId": "pc_1", "design": DESIGN}], "unitCosts": UNIT_COSTS}
    result = c.AreaResult.model_validate(client.post("/api/areas/deccan/rescore", json=body).json())
    assert result.risk == c.RiskInfo(label="MODERATE", index="vci", change=-4.3)
    assert result.parcel_risk is not None and "pc_1" in result.parcel_risk


@pytest.mark.parametrize(
    ("change", "status", "code"),
    [
        ({"kind": "shade", "siteId": "s_missing", "quantity": 1}, 404, "SITE_NOT_FOUND"),
        ({"kind": "shade", "siteId": "s_shade_1", "quantity": 900}, 422, "QUANTITY_OUT_OF_RANGE"),
        ({"kind": "building", "siteId": "pc_9", "design": DESIGN}, 404, "PARCEL_NOT_FOUND"),
        ({"kind": "lawn", "siteId": "s_shade_1", "quantity": 1}, 422, "INVALID_REQUEST"),
    ],
)
def test_rescore_errors_use_contract_codes(client: TestClient, change: dict[str, Any], status: int, code: str) -> None:
    response = client.post("/api/areas/deccan/rescore", json={"changes": [change], "unitCosts": UNIT_COSTS})
    assert response.status_code == status
    error = c.ErrorBody.model_validate(response.json()).error
    assert error.code == code
    assert error.message


def test_engine_stub_is_not_implemented(make_client: Any, engine: Any) -> None:
    def stub(*args: object) -> None:
        raise ecozone_engine.NotImplementedYetError("rescore", "WP5b")

    engine.rescore = stub
    with make_client(engine) as client:
        response = client.post("/api/areas/deccan/rescore", json={"changes": [], "unitCosts": UNIT_COSTS})
    assert response.status_code == 501
    assert response.json()["error"]["code"] == "NOT_IMPLEMENTED"


def test_greedy_returns_a_candidate(client: TestClient) -> None:
    body = {"mode": "repair", "budgetInr": 500_000, "unitCosts": UNIT_COSTS, "quickWinSharePct": 20}
    candidate = c.Candidate.model_validate(client.post("/api/areas/deccan/greedy", json=body).json())
    assert candidate.source == "greedy"
    assert candidate.valid
    assert candidate.changes == [c.InterventionChange(kind="shade", site_id="s_shade_1", quantity=48)]


# ---------- runs ----------

REPAIR_SEARCH = {"mode": "repair", "budgetInr": 500_000, "unitCosts": UNIT_COSTS, "quickWinSharePct": 20}


def test_run_streams_events_in_order_and_saves_the_result(client: TestClient, store: MemoryStore) -> None:
    start = client.post("/api/areas/deccan/runs", json=REPAIR_SEARCH)
    assert start.status_code == 201
    run_id = c.StartRunResponse.model_validate(start.json()).run_id
    with client.stream("GET", f"/api/runs/{run_id}/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        events = sse(response.read().decode())
    assert [e["type"] for e in events] == ["round", "candidate", "round", "done"]
    assert [e["seq"] for e in events] == [1, 2, 3, 4]
    record = store.get_run(run_id)
    assert record is not None and record.result is not None
    assert record.result.best.id == "g1"


def test_run_replays_after_last_event_id(client: TestClient) -> None:
    run_id = client.post("/api/areas/deccan/runs", json=REPAIR_SEARCH).json()["runId"]
    client.get(f"/api/runs/{run_id}/events")
    replay = sse(client.get(f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "2"}).text)
    assert [e["seq"] for e in replay] == [3, 4]


def test_stop_keeps_the_best_result(make_client: Any, engine: Any) -> None:
    with make_client(engine, hold=True) as client:
        run_id = client.post("/api/areas/deccan/runs", json=REPAIR_SEARCH).json()["runId"]
        assert client.delete(f"/api/runs/{run_id}").status_code == 204
        events = sse(client.get(f"/api/runs/{run_id}/events").text)
    assert [e["type"] for e in events] == ["round", "candidate", "done"]
    DoneEvent.model_validate(events[-1])


def test_unknown_run_is_run_not_found(client: TestClient) -> None:
    for response in (client.get("/api/runs/nope/events"), client.delete("/api/runs/nope")):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RUN_NOT_FOUND"


def test_explain_uses_the_runner(client: TestClient) -> None:
    body = {"changes": [{"kind": "shade", "siteId": "s_shade_1", "quantity": 48}], "unitCosts": UNIT_COSTS}
    explanation = c.Explanation.model_validate(client.post("/api/areas/deccan/explain", json=body).json())
    assert explanation.source == "template"


def test_without_agents_runs_end_with_not_implemented(make_client: Any, engine: Any) -> None:
    with make_client(engine) as client:
        run_id = client.post("/api/areas/deccan/runs", json=REPAIR_SEARCH).json()["runId"]
        events = sse(client.get(f"/api/runs/{run_id}/events").text)
        explain = client.post("/api/areas/deccan/explain", json={"changes": [], "unitCosts": UNIT_COSTS})
    assert [(e["type"], e["code"]) for e in events] == [("error", "NOT_IMPLEMENTED")]
    assert explain.status_code == 501


# ---------- snapshot ----------


def test_snapshot_writes_every_mock_file(client: TestClient, tmp_path: Path) -> None:
    from ecozone_api.snapshot import FILES, snapshot

    written = snapshot("deccan", tmp_path / "mock", client)
    assert sorted(p.name for p in written) == sorted(FILES)
    area = json.loads((tmp_path / "mock" / "area.json").read_text())
    assert c.AreaSummary.model_validate(area).mock is True
