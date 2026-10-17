# pipeline/

Offline data job, run once per city. Lane: **D**.

Turns public data into one versioned area bundle (GeoParquet tables plus `meta.json`) that the engine loads at startup: OSM geometry, building heights with their source, blocks, 10 m footpath chunks, classification (parcels, candidate sites, built form), sun table, prevailing wind, and per-block attributes. Does not run in the live request path — see [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

## Run

```
uv run pipeline all --area deccan          # osm → … → bundle → baselines, into data/areas/deccan/v1/
uv run pipeline geometry --area deccan     # one step; each reads the previous step's files from data/work/deccan/
uv run pipeline osm --area deccan --refresh  # download Overpass again (otherwise the cached response is used)
```

Steps in order: `osm`, `sun_wind`, `heights`, `geometry`, `classify`, `attributes`, `bundle`, `baselines`. Options: `--data-dir` (or `ECOZONE_DATA_DIR`), `--config`, `--out`. Raw downloads are cached under `data/work/<area>/raw/` with their fetch date.

## Status

Bundle v1 (OSM only) builds for Deccan and is unchanged. The heat check exists as a separate command, `uv run --extra ee pipeline heat-check --area deccan`, which fetches Landsat surface temperature per block for validation only (needs Earth Engine access and the optional `ee` extra; see [../evals/heat_check/README.md](../evals/heat_check/README.md)); it is not part of `all`. Earth Engine layers for the scores, BigQuery load and GCS upload are not built yet; `meta.json` lists `earth_engine` under `skipped_steps`, and `baselines` stays skipped until the engine implements `load_bundle` and `compute_baselines`.

## Tests

`uv run pytest pipeline`. Everything runs offline on a synthetic area: `tests/fixtures/make_tiny.py` writes `tiny_overpass.json`, `tiny.yaml` and the bundle the engine tests load from `engine/tests/fixtures/tiny/`. Re-run it after a pipeline change that alters the bundle; a test fails if the committed fixture is stale.

**Rules:** [RULES.md](RULES.md) for this folder, on top of [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md).
