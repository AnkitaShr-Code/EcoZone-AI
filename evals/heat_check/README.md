# Heat check

Does the baseline heat index (HEI, no changes applied) rank blocks the way satellite-measured surface temperature does? The method is in [docs/PLANNING.md](../../docs/PLANNING.md#checking-the-heat-index-against-measurement). This folder holds the one table the check reads; the code is `pipeline/src/ecozone_pipeline/steps/earth_engine.py` (fetch) and `evals/test_heat_check.py` with `evals/evalkit/heat_check.py` (statistics).

## Run it

One command, from the repo root, with Earth Engine access (below) and the Deccan bundle built:

```
ECOZONE_DATA_DIR=<dir holding areas/deccan/v1> uv run --extra ee pipeline heat-check --area deccan
```

`ECOZONE_DATA_DIR` defaults to `./data`; set it when the bundle lives in another checkout (or pass `--out <bundle dir>`). The command writes two files into `data/` here, both to be committed:

- `data/deccan_block_lst.csv`: `block_id, lst_kelvin, valid_pixels`, one row per block that has a valid pixel. `lst_kelvin` is the block's median Landsat surface temperature, an internal derived column that is never shown in the app, the docs or REPORT.md. `valid_pixels` is the coverage-weighted count of unmasked 30 m pixels behind it.
- `data/deccan_block_lst.meta.json`: provenance. Dataset ids, date window and years used, scenes per window, the masks and limits, fetch date, Earth Engine project, blocks requested, kept and dropped, and the bundle version and settings hash the blocks came from.

Then run the evals (`uv run python evals/report.py`, or `uv run pytest evals/test_heat_check.py`). Without the CSV the eval skips with the command above and REPORT.md says "Heat check: not run".

## Access

Earth Engine is used only offline, by this command. The Python client is the optional `ee` extra of the pipeline package, so the API image and `pipeline all` never need it. Use either:

- `earthengine authenticate` once on the machine; or
- an OAuth access token in `ECOZONE_EE_ACCESS_TOKEN` (for example `ECOZONE_EE_ACCESS_TOKEN=$(gcloud auth print-access-token)`), which is turned into credentials with the Earth Engine and cloud-platform scopes.

The Google Cloud project is `ECOZONE_EE_PROJECT`, default `ecozone-ai-2026`. The signed-in account needs these roles on it: `roles/serviceusage.serviceUsageConsumer` and `roles/earthengine.viewer`, and the Earth Engine API must be enabled. If initialisation fails the command stops with a message that says so; nothing is written.

## What is computed

- Landsat 8 `LANDSAT/LC08/C02/T1_L2` and Landsat 9 `LANDSAT/LC09/C02/T1_L2`, band `ST_B10`, kelvin = DN x 0.00341802 + 149.0.
- Window: March 1 to May 31 of the bundle's reference year (2026). Scenes with a scene-level `CLOUD_COVER` of 30% or more are not used. If fewer than 5 scenes remain, the same window of 2025 is added; the years used are recorded.
- Pixel masks: `QA_PIXEL` dilated cloud, cirrus, cloud and cloud shadow bits; fill; and `ST_QA` (the per-pixel uncertainty band) negative or above 5 K. USGS publishes `ST_QA` but no pass value, so that limit, like the 30% and 5-scene settings, is our own choice, fixed before any run and not tuned.
- A per-pixel median composite, then the median over each block polygon (reprojected to WGS84) at 30 m in EPSG:32643. Landsat thermal is collected at 100 m and resampled to 30 m, and the smallest blocks are well under one 30 m pixel, so small blocks are mixed measurements; `valid_pixels` shows which. Blocks with no valid pixel are dropped and listed in the provenance file.

## What is reported, and what is not claimed

REPORT.md gets the Spearman rank correlation, the block count and a permutation p-value (10,000 shuffles, fixed seed) for the **test** half of the blocks (the headline; weights were never tuned on either half), then for all blocks and the tune half for context. VCI, GCS and PSS are reported the same way as secondary, pre-declared context. There is no pass mark and the result is reported whatever it is. No engine setting, index or weight is changed after seeing it.

Not claimed: that the heat index predicts air temperature or comfort; that agreement shows the weights are right (the index shares inputs with what drives surface temperature); anything about shade structures (Landsat sees the top of a structure, not the ground under it); anything beyond the Deccan demo area; and any absolute temperature, which never appears outside the CSV. Each Landsat scene is a single late-morning overpass, and 33 test blocks is a small sample. In bundle v1 the roof reflectance is a labelled default and the paving and green inputs are OSM-derived proxies, because the Earth Engine layers for scores are not built.
