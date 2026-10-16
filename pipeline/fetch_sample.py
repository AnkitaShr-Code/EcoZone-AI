"""Fetch a small real OSM sample for the map overlay prototype.

Downloads buildings, roads, parks and waiting points for one bounding box
from the Overpass API and writes a single GeoJSON file. Standard library only.

Usage:
    python3 pipeline/fetch_sample.py [south west north east] [out_path]
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BBOX = (18.5165, 73.8380, 18.5245, 73.8480)  # south, west, north, east
DEFAULT_OUT = "app/scripts/source/deccan.osm.geojson"
OVERPASS = "https://overpass-api.de/api/interpreter"
ROAD_CLASSES = (
    "trunk|primary|secondary|tertiary|unclassified|residential|living_street|"
    "trunk_link|primary_link|secondary_link|tertiary_link"
)
# Width in metres by road class, used where OSM has no width tag (prototype settings).
ROAD_WIDTH_M = {
    "trunk": 24, "primary": 20, "secondary": 16, "tertiary": 12,
    "unclassified": 9, "residential": 8, "living_street": 6,
}
WAIT_WEIGHTS = {"school": 3, "college": 2, "hospital": 3, "clinic": 2, "marketplace": 2, "bus_stop": 1}
METRES_PER_FLOOR = 3.0


def query(bbox):
    s, w, n, e = bbox
    b = f"{s},{w},{n},{e}"
    return f"""[out:json][timeout:90];
(
  way["building"]({b});
  way["highway"~"^({ROAD_CLASSES})$"]({b});
  way["leisure"="park"]({b});
  way["landuse"~"^(grass|recreation_ground)$"]({b});
  node["highway"="bus_stop"]({b});
  nwr["amenity"~"^(school|college|hospital|clinic|marketplace)$"]({b});
);
out geom tags;"""


def fetch(bbox, attempts=4):
    data = urllib.parse.urlencode({"data": query(bbox)}).encode()
    req = urllib.request.Request(
        OVERPASS, data=data,
        headers={"User-Agent": "EcoZoneAI-prototype/0.1 (AI Builder Cup 2026)", "Accept": "application/json"},
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            # Overpass returns 429/502/504 under load; back off and retry.
            if err.code not in (429, 502, 503, 504) or attempt == attempts - 1:
                raise
            time.sleep(10 * (attempt + 1))


def height_m(tags):
    """Height from OSM tags; None when OSM has no height information."""
    for key in ("height", "building:height"):
        if key in tags:
            try:
                return float(tags[key].split()[0])
            except ValueError:
                pass
    if "building:levels" in tags:
        try:
            return float(tags["building:levels"]) * METRES_PER_FLOOR
        except ValueError:
            pass
    return None


def centroid(coords):
    return [sum(c[0] for c in coords) / len(coords), sum(c[1] for c in coords) / len(coords)]


def to_features(osm):
    features = []
    for el in osm["elements"]:
        tags = el.get("tags", {})
        if el["type"] == "way" and "geometry" in el:
            coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
            closed = len(coords) > 3 and coords[0] == coords[-1]
            if "building" in tags and closed:
                h = height_m(tags)
                features.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [coords]},
                                 "properties": {"kind": "building", "id": el["id"], "height_m": h,
                                                "height_source": "osm" if h is not None else "default"}})
            elif "highway" in tags:
                cls = tags["highway"].replace("_link", "")
                features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords},
                                 "properties": {"kind": "road", "id": el["id"], "class": cls,
                                                "name": tags.get("name"),
                                                "width_m": ROAD_WIDTH_M.get(cls, 8)}})
            elif closed and (tags.get("leisure") == "park" or "landuse" in tags):
                features.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [coords]},
                                 "properties": {"kind": "green", "id": el["id"], "name": tags.get("name")}})
            elif "amenity" in tags:
                features.append(wait_point(el["id"], tags["amenity"], tags, centroid(coords)))
        elif el["type"] == "node":
            kind = "bus_stop" if tags.get("highway") == "bus_stop" else tags.get("amenity")
            if kind in WAIT_WEIGHTS:
                features.append(wait_point(el["id"], kind, tags, [el["lon"], el["lat"]]))
        elif el["type"] == "relation" and "amenity" in tags and "bounds" in el:
            bd = el["bounds"]
            pt = [(bd["minlon"] + bd["maxlon"]) / 2, (bd["minlat"] + bd["maxlat"]) / 2]
            features.append(wait_point(el["id"], tags["amenity"], tags, pt))
    return features


def wait_point(osm_id, kind, tags, lonlat):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": lonlat},
            "properties": {"kind": "wait_point", "id": osm_id, "type": kind,
                           "weight": WAIT_WEIGHTS.get(kind, 1), "name": tags.get("name")}}


def main():
    args = sys.argv[1:]
    bbox = tuple(float(a) for a in args[:4]) if len(args) >= 4 else DEFAULT_BBOX
    out = args[4] if len(args) >= 5 else DEFAULT_OUT
    features = to_features(fetch(bbox))
    fc = {"type": "FeatureCollection", "bbox": [bbox[1], bbox[0], bbox[3], bbox[2]], "features": features,
          "attribution": "© OpenStreetMap contributors, ODbL"}
    with open(out, "w") as f:
        json.dump(fc, f)
    counts = {}
    for ft in features:
        counts[ft["properties"]["kind"]] = counts.get(ft["properties"]["kind"], 0) + 1
    tagged = sum(1 for ft in features if ft["properties"]["kind"] == "building" and ft["properties"]["height_m"] is not None)
    print(f"wrote {out}: {counts}; buildings with an OSM height: {tagged}")


if __name__ == "__main__":
    main()
