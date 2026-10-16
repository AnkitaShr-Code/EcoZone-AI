from __future__ import annotations

import json

import numpy as np
from shapely import Polygon
from tiny_area import FIXTURES, Tiny

from ecozone_pipeline.config import load_config
from ecozone_pipeline.steps import osm


def test_tiny_extract_counts(tiny: Tiny) -> None:
    counts = json.loads(tiny.paths.json("osm").read_text())["counts"]
    assert counts == {
        "buildings": 24,
        "roads": 3,
        "sidewalks": 1,
        "green": 1,
        "water": 0,
        "wait_points": 3,
        "public_land": 2,
        "vacant": 1,
        "trees": 3,
    }


def test_wait_point_kinds_and_weights(tiny: Tiny) -> None:
    wp = tiny.table("osm_wait_points").set_index("kind")
    assert set(wp.index) == {"bus_stop", "hospital", "school"}
    assert wp.loc["school", "weight"] == 3
    assert wp.loc["bus_stop", "weight"] == 1


def test_everything_is_clipped_to_the_box(tiny: Tiny) -> None:
    box = osm.bbox_polygon(tiny.cfg).buffer(0.01)
    for name in ("buildings", "roads", "sidewalks", "green", "public_land"):
        assert tiny.table(f"osm_{name}").geometry.within(box).all(), name


def test_ids_are_unique(tiny: Tiny) -> None:
    for name in ("buildings", "roads", "wait_points"):
        assert tiny.table(f"osm_{name}")["id"].is_unique


def test_school_building_is_not_school_grounds(tiny: Tiny) -> None:
    land = tiny.table("osm_public_land")
    assert sorted(land["kind"]) == ["parking", "school_grounds"]
    assert land.loc[land["kind"] == "school_grounds", "geometry"].iloc[0].area > 1000


def test_osm_number_parsing() -> None:
    assert osm._float("12") == 12.0
    assert osm._float("12.5 m") == 12.5
    assert osm._float("9;12") == 9.0
    assert np.isnan(osm._float("tall"))
    assert np.isnan(osm._float(None))


def test_multipolygon_relation_with_a_hole() -> None:
    def ring(x0: float, y0: float, x1: float, y1: float) -> list[dict[str, float]]:
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        return [{"lon": x, "lat": y} for x, y in pts]

    relation = {
        "type": "relation",
        "id": 1,
        "tags": {"type": "multipolygon", "leisure": "park"},
        "members": [
            {"type": "way", "role": "outer", "geometry": ring(0, 0, 4, 4)},
            {"type": "way", "role": "inner", "geometry": ring(1, 1, 2, 2)},
        ],
    }
    geom = osm._area_geometry(relation)
    assert isinstance(geom, Polygon)
    assert geom.area == 15.0


def test_overpass_query_covers_every_table() -> None:
    query = osm.overpass_query(load_config("tiny", FIXTURES / "tiny.yaml"))
    for needle in ('"building"', '"highway"', '"sidewalk"', '"leisure"', '"natural"="tree"', '"bus_stop"', "parking"):
        assert needle in query
