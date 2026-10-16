from __future__ import annotations

import math

import numpy as np
from shapely import LineString, Point
from tiny_area import Tiny

from ecozone_pipeline.steps.geometry import bearing_deg, chunk_line, junction_zones, split_roads


def test_bearing_is_clockwise_from_north() -> None:
    assert bearing_deg((0, 0), (0, 10)) == 0
    assert bearing_deg((0, 0), (10, 0)) == 90
    assert bearing_deg((0, 0), (0, -10)) == 180
    assert bearing_deg((0, 0), (-10, 0)) == 270


def test_chunk_line_lengths() -> None:
    pieces = chunk_line(LineString([(0, 0), (0, 25)]), 10, 2)
    assert [round(p.length, 6) for p in pieces] == [10, 10, 5]


def test_chunk_line_drops_a_remainder_under_the_minimum() -> None:
    pieces = chunk_line(LineString([(0, 0), (0, 21)]), 10, 2)
    assert [round(p.length, 6) for p in pieces] == [10, 10]


def test_blocks_come_from_the_road_network(tiny: Tiny) -> None:
    blocks = tiny.table("blocks_geom")
    assert len(blocks) == 6
    assert list(blocks["id"]) == [f"blk_{i:04d}" for i in range(1, 7)]
    road_surface = tiny.table("osm_roads").geometry.buffer(3.9).union_all()
    assert blocks.geometry.intersection(road_surface.buffer(-0.5)).area.max() < 1e-3


def test_chunks_respect_length_limits(tiny: Tiny) -> None:
    chunks = tiny.table("chunks")
    assert chunks["length_m"].between(2, 10 + 1e-6).all()
    assert np.allclose(chunks.geometry.length, chunks["length_m"])


def test_chunks_stay_clear_of_junctions(tiny: Tiny) -> None:
    zone = junction_zones(split_roads(tiny.table("osm_roads")), tiny.cfg)
    assert not zone.is_empty
    assert not tiny.table("chunks").geometry.intersects(zone.buffer(-0.01)).any()


def test_junction_zones_are_at_the_two_crossings(tiny: Tiny) -> None:
    zone = junction_zones(split_roads(tiny.table("osm_roads")), tiny.cfg)
    assert len(zone.geoms) == 2
    assert all(g.area > math.pi * 10**2 for g in zone.geoms)


def test_osm_sidewalk_replaces_derived_line_where_it_exists(tiny: Tiny) -> None:
    chunks = tiny.table("chunks")
    osm_chunks = chunks[chunks["footpath_source"] == "osm"]
    assert len(osm_chunks) > 0
    assert (osm_chunks["side"] == "right").all()
    assert set(chunks["footpath_source"]) == {"osm", "derived"}


def test_every_chunk_has_a_block_and_street_ratio(tiny: Tiny) -> None:
    chunks = tiny.table("chunks")
    assert chunks["block_id"].notna().all()
    assert (chunks["H_W"] >= 0).all()
    assert chunks["H_W"].max() > 1  # the five-storey lane
    assert chunks["H_W"].min() < 1


def test_near_wait_flags_the_bus_stop(tiny: Tiny) -> None:
    chunks = tiny.table("chunks")
    near = chunks[chunks["near_wait"]]
    assert len(near) > 0
    stop = Point(*tiny.table("osm_wait_points").set_index("kind").loc["bus_stop", "geometry"].coords[0])
    assert near.geometry.distance(stop).min() < 30


def test_bearings_follow_the_streets(tiny: Tiny) -> None:
    chunks = tiny.table("chunks")
    axis = chunks["bearing_deg"] % 180
    off = np.minimum(np.abs(axis - 90), np.minimum(axis, 180 - axis))
    assert (off < 5).all(), "tiny area has only north-south and east-west streets"


def test_geometry_is_deterministic(tiny: Tiny) -> None:
    from ecozone_pipeline.steps import geometry

    before = tiny.table("chunks")
    geometry.run(tiny.cfg, tiny.paths)
    after = tiny.table("chunks")
    assert list(before["id"]) == list(after["id"])
    assert before.geometry.geom_equals(after.geometry).all()
