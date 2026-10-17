from __future__ import annotations

import pytest
from tiny_area import Tiny

from ecozone_pipeline.steps.heights import HEIGHT_SOURCES, typology_floors


@pytest.fixture
def typology() -> dict[str, object]:
    return {
        "default_floors": 3,
        "rules": [
            {"building": ["shed"], "floors": 1},
            {"building": "any", "max_footprint_m2": 60, "floors": 2},
            {"building": ["hospital"], "min_footprint_m2": 200, "floors": 5},
            {"building": "any", "floors": 3},
        ],
    }


def test_typology_first_matching_rule_wins(typology: dict[str, object]) -> None:
    assert typology_floors("shed", 500, typology) == 1
    assert typology_floors("house", 40, typology) == 2
    assert typology_floors("hospital", 300, typology) == 5
    assert typology_floors("hospital", 100, typology) == 3


def test_height_chain_and_sources(tiny: Tiny) -> None:
    b = tiny.table("heights").set_index("id")
    assert set(b["height_source"]) <= set(HEIGHT_SOURCES)
    hospital = b[b["building_tag"] == "hospital"].iloc[0]
    assert (hospital["height_m"], hospital["height_source"]) == (15.0, "osm_height")
    levels = b[b["height_source"] == "osm_levels"]
    assert (levels["height_m"] % 3 == 0).all()
    assert (b["height_m"] > 0).all()


def test_typology_rows_use_footprint(tiny: Tiny) -> None:
    b = tiny.table("heights")
    shed = b[b["building_tag"] == "shed"].iloc[0]
    assert shed["height_source"] == "typology"
    assert shed["height_m"] == 3.0


def test_roof_albedo_is_labeled_default(tiny: Tiny) -> None:
    b = tiny.table("heights")
    assert (b["roof_albedo_source"] == "typology_default").all()
    assert b["roof_albedo"].between(0, 1).all()
