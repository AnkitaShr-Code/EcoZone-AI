# pipeline/ rules

Package `ecozone_pipeline`. The offline job that turns public data into one area bundle. Everything in [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md) applies; this file adds what is specific here.

## Layout

```
pipeline/
  config/deccan.yaml         bbox, CRS, reference date and times, wind season, road-class widths, typology heights, site rules
  config/unit_costs.yaml     default unit costs, one row per intervention, each with source, date and URL
  src/ecozone_pipeline/
    cli.py                   `uv run pipeline <step|all> --area deccan`
    steps/osm.py             extract: buildings, roads, sidewalks, green, water, waiting points, public land
    steps/geometry.py        blocks (polygonize), footpath runs, 10 m chunks, road widths, canyon axis, H/W
    steps/heights.py         height fallback chain with height_source
    steps/classify.py        parcels, candidate sites per site rule, built-form class
    steps/sun_wind.py        pvlib sun table; Open-Meteo prevailing wind
    steps/earth_engine.py    optional: Open Buildings heights, S2 shares, roof albedo, WorldCover, Landsat LST, clips
    steps/attributes.py      per-block attributes
    steps/baselines.py       baseline scores by calling ecozone_engine
    steps/bundle.py          write GeoParquet + meta.json; upload to GCS
    steps/bigquery.py        load the bundle into ecozone_<area> (analytics copy)
  fetch_sample.py            legacy stdlib fetcher for the UI mock; removed when the mock becomes an engine snapshot
```

## Rules

- **Steps are idempotent and cached.** Each step reads the previous step's output from `data/work/<area>/` and writes its own. Re-running a step with the same inputs produces the same files. Raw downloads (Overpass, Open-Meteo, EE exports) are saved with their fetch date and never re-fetched unless `--refresh`.
- **Config, not code, per area.** Onboarding an area changes YAML only. Code that branches on an area name is a review blocker.
- **Baselines use the engine.** `baselines.py` builds an `AreaModel` and calls engine functions. The pipeline never computes VCI, HEI, GCS, PSS, priority or ACS itself.
- **Sources are recorded.** `meta.json` lists every source with licence, URL, fetch date and the version or snapshot used. OSM attribution text is stored there for the API.
- **Gaps are counted, not hidden.** Every fallback (height by typology, footpath derived from a road edge, default albedo, width from road class) is a source column on the row and a count in `meta.json` `data_gaps`.
- **Optional steps declare themselves.** If Earth Engine is unavailable the step records `skipped: earth_engine` in `meta.json` and the bundle still builds, with defaults labeled.
- **Geometry hygiene.** Clip chunks 10 m back from junctions; drop chunks under 2 m; make every polygon valid (`shapely.make_valid`) and drop empties before writing.

## Height fallback chain

`osm_height` (OSM `height`) → `osm_levels` (`building:levels` × 3 m) → `open_buildings` (2.5D Temporal via EE, when available) → `typology` (default floors from `config/<area>.yaml` by building tag and footprint size). The typology table is a prototype setting and is listed in the deck's data caveats.

## Bundle tables

All geometry in EPSG:32643. Ids are stable strings prefixed by type (`b_`, `blk_`, `ch_`, `wp_`, `pc_`, `s_`).

| Table | Key columns |
| --- | --- |
| `buildings` | id, geometry, height_m, height_source, building_tag, footprint_m2, block_id, roof_albedo, roof_albedo_source |
| `blocks` | id, geometry, area_m2, coverage, built_form (`dense_low_rise`/`other`), I_s, G_c, G_buf (all 0–100), d_green, d_water (m, capped), H_W, canyon_axis_deg (0–180), L_built (m), V (m³), roof_albedo, wait_weight (Σ weights within 150 m), split (tune/test), building_count, median_footprint_m2, median_floors, and one `*_source` column per attribute |
| `chunks` | id, geometry, run_id, block_id, road_name, road_class, road_width_m, width_source, bearing_deg (0–360, direction of the run), side (left/right of the road's direction), length_m, H_W, near_wait, footpath_source (osm/derived) |
| `wait_points` | id, geometry, kind, name, weight |
| `parcels` | id, geometry, block_id, area_m2, road_name, road_width_m, street_bearing_deg (0–180), neighbour_height_m, vacant_tag, name |
| `sites` | id, geometry, kind, name, quantity_min, quantity_max, rule, rejected, wait_point_id, H_W, block_id, time_to_benefit (weeks/season/years). A rejected tree row has `rejected` true and `rule` `CANOPY_OBSTRUCTION` |
| `meta.json` | area id and name, city, bbox (WGS84 and UTM), reference date, shade times, sun table, wind_from_deg, V_ref, metres_per_floor, counts, buildings_by_height_source, derived_footpath_chunks, settings hash, pipeline git SHA, sources, data_gaps, skipped_steps, attribution |
| `baselines.parquet` (optional) | block_id, vci, hei, gcs, pss; written by `baselines.py` once the engine can compute them, with `baseline_area` in `meta.json` |

Tables carry a few columns beyond the minimum the engine needs (`name`, `*_source`, `rejected`); the engine ignores what it doesn't use. Dropping or renaming a column is a bundle-schema change and its own PR.

## Tests

- Each step has a test on a small cached Overpass response committed under `pipeline/tests/fixtures/`.
- A bundle-schema test checks every table's columns and types and that every geometry is valid and non-empty.
