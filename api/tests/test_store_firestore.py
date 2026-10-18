"""Unit tests for FirestoreStore (fake client) and an optional cloud test."""

import logging
import os
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

import ecozone_contract as c
from ecozone_contract.runs import RepairSearchRequest
from ecozone_api.store import RunRecord
from ecozone_api.store.firestore import FirestoreStore, _to_doc

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unit_cost(inr: float) -> c.UnitCost:
    return c.UnitCost(unit="tree", inr=inr, source="BMC USOR 2023")


def _make_record(run_id: str = "abc123") -> RunRecord:
    request = RepairSearchRequest(
        mode="repair",
        budget_inr=250_000.0,
        unit_costs=c.UnitCosts(
            tree_row=_unit_cost(8_000),
            shade=_unit_cost(4_500),
            depave=_unit_cost(1_200),
            pocket_green=_unit_cost(2_500),
            cool_roof=_unit_cost(950),
        ),
        quick_win_share_pct=20.0,
    )
    candidate = c.Candidate(
        id="g1",
        round=1,
        source="gemini",
        label="Shade at the bus stop",
        changes=[c.InterventionChange(kind="shade", site_id="s_shade_1", quantity=48)],
        score=45.1,
        cost_inr=216_000.0,
        valid=True,
    )
    explanation = c.Explanation(
        paragraphs=["Shade at the bus stop covers the main waiting point."],
        drivers=[],
        source="gemini",
    )
    result = c.SearchResult(
        best=candidate,
        gemini_beat_greedy=True,
        rejected=[],
        rounds=2,
        explanation=explanation,
    )
    return RunRecord(
        run_id=run_id,
        area_id="deccan",
        request=request,
        result=result,
        finished_at=datetime(2026, 10, 18, 9, 0, 0, tzinfo=UTC),
    )


def _fake_client() -> MagicMock:
    """Returns a MagicMock whose .collection().document().set() chain records calls."""
    client = MagicMock()
    return client


# ---------------------------------------------------------------------------
# Unit tests (fake client)
# ---------------------------------------------------------------------------


def test_save_run_writes_to_memory() -> None:
    store = FirestoreStore(_client=_fake_client())
    record = _make_record()
    store.save_run(record)
    assert store.get_run(record.run_id) is record


def test_save_run_calls_firestore_set() -> None:
    client = _fake_client()
    store = FirestoreStore(_client=client)
    record = _make_record("run_xyz")
    store.save_run(record)
    client.collection.assert_called_once_with("runs")
    client.collection().document.assert_called_once_with("run_xyz")
    client.collection().document().set.assert_called_once()
    doc = client.collection().document().set.call_args[0][0]
    assert doc["run_id"] == "run_xyz"
    assert doc["area_id"] == "deccan"
    assert doc["result"]["best"]["source"] == "gemini"


def test_to_doc_shape() -> None:
    record = _make_record("r1")
    doc = _to_doc(record)
    assert doc["run_id"] == "r1"
    assert doc["area_id"] == "deccan"
    assert doc["finished_at"] == record.finished_at
    assert isinstance(doc["request"], dict)
    assert doc["request"]["mode"] == "repair"
    assert isinstance(doc["result"], dict)
    assert doc["result"]["rounds"] == 2


def test_to_doc_none_result() -> None:
    record = _make_record()
    no_result = RunRecord(
        run_id=record.run_id,
        area_id=record.area_id,
        request=record.request,
        result=None,
        finished_at=record.finished_at,
    )
    doc = _to_doc(no_result)
    assert doc["result"] is None


def test_firestore_failure_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    client = _fake_client()
    client.collection.return_value.document.return_value.set.side_effect = RuntimeError("network error")
    store = FirestoreStore(_client=client)
    record = _make_record()
    with caplog.at_level(logging.WARNING, logger="ecozone_api.store.firestore"):
        store.save_run(record)  # must not raise
    assert store.get_run(record.run_id) is record  # memory write still succeeded
    assert "firestore write failed" in caplog.text


def test_get_run_miss_returns_none() -> None:
    store = FirestoreStore(_client=_fake_client())
    assert store.get_run("no_such_run") is None


def test_multiple_runs_stored_independently() -> None:
    store = FirestoreStore(_client=_fake_client())
    r1 = _make_record("r1")
    r2 = _make_record("r2")
    store.save_run(r1)
    store.save_run(r2)
    assert store.get_run("r1") is r1
    assert store.get_run("r2") is r2


# ---------------------------------------------------------------------------
# Cloud test — gated on ECOZONE_CLOUD_TESTS=1
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("ECOZONE_CLOUD_TESTS") != "1",
    reason="set ECOZONE_CLOUD_TESTS=1 and have ADC for ecozone-ai-2026 to run cloud tests",
)
def test_cloud_firestore_roundtrip() -> None:
    """Writes and reads back a RunRecord on the real Firestore (default) database."""
    store = FirestoreStore(project="ecozone-ai-2026")
    record = _make_record(f"test_run_{int(datetime.now(UTC).timestamp())}")
    store.save_run(record)

    # Verify via memory (live source)
    assert store.get_run(record.run_id) is record

    # Verify in Firestore directly
    from google.cloud import firestore as fs  # type: ignore[import-untyped]

    db = fs.Client(project="ecozone-ai-2026", database="(default)")
    snap = db.collection("runs").document(record.run_id).get()
    assert snap.exists
    doc = snap.to_dict()
    assert doc is not None
    assert doc["run_id"] == record.run_id
    assert doc["area_id"] == "deccan"
    assert doc["result"]["rounds"] == 2

    # Clean up the test document
    db.collection("runs").document(record.run_id).delete()
