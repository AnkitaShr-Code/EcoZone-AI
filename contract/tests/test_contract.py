"""Contract checks from ENGINEERING_RULES.md §6–7 and §9: fixtures validate, openapi.json is fresh,
and no planner-facing string carries a forbidden unit or approval language."""

import json
import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, TypeAdapter

import ecozone_contract as c
from ecozone_contract.export import OPENAPI_PATH, render

MOCK_DIR = Path(__file__).resolve().parents[2] / "app" / "public" / "mock" / "deccan"

FIXTURES: dict[str, Any] = {
    "area.json": c.AreaSummary,
    "blocks.json": c.BlockLayer,
    "segments.json": c.SegmentLayer,
    "buildings.json": c.BuildingLayer,
    "wait-points.json": c.WaitPointLayer,
    "parcels.json": c.ParcelLayer,
    "shadows-1300.json": c.ShadowLayer,
    "shadows-1500.json": c.ShadowLayer,
    "shadows-1600.json": c.ShadowLayer,
    "sites.json": list[c.Site],
    "hotspots.json": list[c.Hotspot],
}

# ENGINEERING_RULES.md §7: no temperature, wind-speed or energy units; no approval language.
FORBIDDEN = re.compile(
    r"°\s*C|℃|\bdegrees? Celsius\b|\bm/s\b|\bkm/h\b|\bkWh\b|W/m²|\b(approve[ds]?|denie[ds]|deny|sanction(ed)?)\b",
    re.IGNORECASE,
)


def _load(name: str) -> Any:
    return json.loads((MOCK_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_mock_fixture_validates(name: str) -> None:
    TypeAdapter(FIXTURES[name]).validate_python(_load(name))


def test_every_contract_fixture_is_checked() -> None:
    served = {p.name for p in MOCK_DIR.glob("*.json") if not p.name.startswith("_")}
    assert served == set(FIXTURES), "a mock file without a contract model, or a model without a fixture"


def test_openapi_is_fresh() -> None:
    assert OPENAPI_PATH.read_text(encoding="utf-8") == render(), "run `uv run ecozone-contract export`"


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, BaseModel):
        return _strings(value.model_dump())
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list | tuple):
        return [s for v in value for s in _strings(v)]
    return []


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_no_forbidden_units_or_approval_language(name: str) -> None:
    hits = [s for s in _strings(_load(name)) if FORBIDDEN.search(s)]
    assert not hits, hits[:5]


@pytest.mark.parametrize(
    ("text", "bad"),
    [
        ("Footpath shade rises from 17 to 31.", False),
        ("It will be 2 °C cooler.", True),
        ("Wind at 3 m/s", True),
        ("The planner approves the plan.", True),
        ("Recommended; the planner decides.", False),
    ],
)
def test_forbidden_pattern(text: str, bad: bool) -> None:
    assert bool(FORBIDDEN.search(text)) is bad


def test_change_union_round_trips() -> None:
    adapter = TypeAdapter(c.Change)
    building = adapter.validate_python(
        {
            "kind": "building",
            "siteId": "pc01",
            "design": {"floors": 12, "footprintPct": 60, "greenPct": 10, "orientationDeg": 45},
        }
    )
    assert isinstance(building, c.BuildingChange)
    assert adapter.dump_python(building)["design"]["footprintPct"] == 60
    tree = adapter.validate_python({"kind": "tree_row", "siteId": "st_1", "quantity": 20})
    assert isinstance(tree, c.InterventionChange)


def test_models_reject_unknown_fields() -> None:
    with pytest.raises(ValueError, match="extra"):
        c.UnitCost.model_validate({"unit": "tree", "inr": 1, "source": "x", "surprise": 1})


def test_unit_cost_keys_match_intervention_types() -> None:
    keys = set(c.UnitCosts.model_json_schema(mode="serialization")["properties"])
    assert keys == {"tree_row", "shade", "depave", "pocket_green", "cool_roof"}
