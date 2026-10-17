"""Generate the tiny synthetic area used by tests and by the engine's fixture bundle.

Run from the repo root after changing the layout or `config/deccan.yaml`:

    uv run python pipeline/tests/fixtures/make_tiny.py

Writes `tiny_overpass.json` (an Overpass-shaped response) and `tiny.yaml` (the config that reads it) next to this
file, then builds the bundle the engine tests load into `engine/tests/fixtures/tiny/`. The layout is in metres from
the south-west corner: three roads cross to make two junctions and six blocks.

    y=240 +------------+-----------+   top row:    park + tall frontage (left), a 10 m x 10 m shed in open land (right)
    y=180 ==== r2 residential (8 m) ===
          | mid-left   | mid-right |   mid row:    parking, vacant plot, 5-storey frontage | school grounds + school
    y=60  ==== r1 tertiary (12 m) ====
          | dense low  | hospital  |   bottom row: 14 small buildings (dense low-rise)     | hospital, bus stop
    y=0   +------------+-----------+
         x=0         x=120 (r3 tertiary, N-S)    x=240
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from ecozone_pipeline.cli import STEPS, run_step
from ecozone_pipeline.config import Paths, load_config

HERE = Path(__file__).parent
ENGINE_FIXTURE = HERE.parents[2] / "engine" / "tests" / "fixtures" / "tiny"
FIXTURE_SHA = "tiny-fixture"
LON0, LAT0 = 73.8400, 18.5180
M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(LAT0))
SIZE_M = 240.0


def lonlat(x: float, y: float) -> dict[str, float]:
    return {"lon": LON0 + x / M_PER_DEG_LON, "lat": LAT0 + y / M_PER_DEG_LAT}


def way(osm_id: int, pts: list[tuple[float, float]], tags: dict[str, str], *, closed: bool) -> dict[str, Any]:
    ring = [*pts, pts[0]] if closed else pts
    return {"type": "way", "id": osm_id, "tags": tags, "geometry": [lonlat(x, y) for x, y in ring]}


def rect(x: float, y: float, w: float, h: float) -> list[tuple[float, float]]:
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def elements() -> list[dict[str, Any]]:
    els: list[dict[str, Any]] = []
    nid = iter(range(1, 10_000))

    for name, pts, cls in (
        ("Road One", [(-10, 60), (120, 60), (250, 60)], "tertiary"),
        ("Road Two", [(-10, 180), (120, 180), (250, 180)], "residential"),
        ("Road Three", [(120, -10), (120, 60), (120, 180), (120, 250)], "tertiary"),
    ):
        els.append(way(next(nid), pts, {"highway": cls, "name": name}, closed=False))
    els.append(way(next(nid), [(20, 54), (100, 54)], {"highway": "footway", "footway": "sidewalk"}, closed=False))

    for row, y in enumerate((10, 30)):  # dense low-rise block: 14 houses of 11 m x 15 m
        for col in range(7):
            tags = {"building": "yes"}
            if row == 0 and col == 0:
                tags["building:levels"] = "2"
            els.append(way(next(nid), rect(3 + 15 * col, y, 11, 15), tags, closed=True))

    els.append(
        way(
            next(nid),
            rect(140, 10, 30, 20),
            {"building": "hospital", "amenity": "hospital", "height": "15", "name": "Test Hospital"},
            closed=True,
        )
    )
    for i in range(4):  # five-storey frontage on the south side of Road Two
        els.append(
            way(next(nid), rect(5 + 25 * i, 150, 20, 20), {"building": "yes", "building:levels": "5"}, closed=True)
        )
    for i in range(3):  # and on the north side
        els.append(
            way(next(nid), rect(70 + 14 * i, 188, 12, 20), {"building": "yes", "building:levels": "5"}, closed=True)
        )
    els.append(way(next(nid), rect(145, 85, 15, 10), {"building": "school"}, closed=True))
    els.append(way(next(nid), rect(200, 200, 10, 10), {"building": "shed"}, closed=True))

    els.append(way(next(nid), rect(40, 90, 30, 20), {"amenity": "parking", "name": "Test Parking"}, closed=True))
    els.append(way(next(nid), rect(80, 80, 24, 24), {"landuse": "greenfield"}, closed=True))
    els.append(way(next(nid), rect(140, 80, 35, 35), {"amenity": "school", "name": "Test School"}, closed=True))
    els.append(way(next(nid), rect(10, 195, 50, 40), {"leisure": "park", "name": "Test Park"}, closed=True))
    for x, y in ((20, 205), (30, 215), (45, 225)):
        els.append({"type": "node", "id": next(nid), "tags": {"natural": "tree"}, **lonlat(x, y)})
    els.append(
        {"type": "node", "id": next(nid), "tags": {"highway": "bus_stop", "name": "Test Stop"}, **lonlat(150, 56)}
    )
    return els


def config() -> dict[str, Any]:
    cfg = yaml.safe_load((HERE.parents[1] / "config" / "deccan.yaml").read_text(encoding="utf-8"))
    east, north = LON0 + SIZE_M / M_PER_DEG_LON, LAT0 + SIZE_M / M_PER_DEG_LAT
    cfg["area"].update(id="tiny", name="Tiny synthetic area (tests)", city="Test", bbox_wgs84=[LON0, LAT0, east, north])
    cfg["wind"]["from_deg"] = 300.0
    cfg["osm"]["source_file"] = "tiny_overpass.json"
    cfg["classify"]["split_seed"] = "ecozone-tiny"
    return cfg


def main() -> None:
    (HERE / "tiny_overpass.json").write_text(
        json.dumps({"version": 0.6, "generator": "make_tiny.py", "elements": elements()}, indent=1) + "\n",
        encoding="utf-8",
    )
    header = "# Generated by make_tiny.py from config/deccan.yaml; do not edit by hand.\n"
    (HERE / "tiny.yaml").write_text(header + yaml.safe_dump(config(), sort_keys=False), encoding="utf-8")

    os.environ["ECOZONE_PIPELINE_SHA"] = FIXTURE_SHA
    cfg = load_config("tiny", HERE / "tiny.yaml")
    with tempfile.TemporaryDirectory() as tmp:
        paths = Paths.for_area(cfg.area_id, Path(tmp))
        for step in STEPS:
            run_step(step, cfg, paths, False, ENGINE_FIXTURE)


if __name__ == "__main__":
    main()
