# pipeline/

Offline data job, run once per city. Lane: **D**.

Turns public data (OpenStreetMap, Google Open Buildings, Sentinel-2, ESA WorldCover, Open-Meteo, Landsat) into BigQuery tables and Cloud Storage bundles for one city: geometry (blocks, footpath segments), classification (parcels, candidate sites, built-form class), Earth Engine layers, wind/sun, baseline attributes and shadows, and heat-check validation.

Not yet implemented. Planned structure and file-by-file detail: [../docs/DESIGN.md](../docs/DESIGN.md#c1-pipeline-offline). Does not run in the live request path — see [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

**Rules:** [RULES.md](RULES.md) for this folder, on top of [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md).
