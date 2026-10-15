# engine/ rules

Package `ecozone_engine`. The deterministic scoring engine and the only place a number is made. Everything in [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md) applies; this file adds what is specific here. Formulas: [../docs/PLANNING.md](../docs/PLANNING.md#scoring-engine), and nowhere else.

## Layout

```
engine/src/ecozone_engine/
  settings.py        every prototype setting, each citing its PLANNING.md section; one frozen dataclass
  model.py           AreaModel (frozen): arrays + STRtree indexes; Change, AreaResult and other result dataclasses
  io.py              load_bundle(path) → AreaModel   (the only module that touches geopandas/pyarrow)
  sun.py             shadow offset vector from a sun table entry (pvlib stays in pipeline)
  shadows.py         building, crown and structure shadow polygons
  shade.py           chunk shading per reference time, PSS per chunk, block and area
  indices.py         vci(), hei(), gcs(), pss aggregation, as pure functions of attributes
  interventions.py   one apply_* per intervention type → AttributeDelta + new shadow geometry
  building.py        apply_building() for Protect
  rescore.py         rescore(area, changes, unit_costs) → AreaResult
  priority.py        priority(), acs(), risk_label()
  drivers.py         driver tag rules
  greedy.py          greedy_baseline(area, budget, unit_costs, sites)
  costs.py           cost of a change set from planner unit costs
engine/tests/
  fixtures/tiny/     hand-built mini area (bundle format)
```

## Rules

- **Pure.** No I/O outside `io.py`, no network, no logging side effects in scoring code, no global mutable state. Functions take the `AreaModel` and return new values; the `AreaModel` is never mutated. A `rescore` call copies only the attributes it changes.
- **Allowed imports**: standard library, `numpy`, `shapely`; `geopandas` and `pyarrow` in `io.py` only. Anything else needs a line here saying why.
- **Units.** Metres and square metres in EPSG:32643; angles in degrees, bearings clockwise from north; sun azimuth in the same convention. Variable names carry the unit when it isn't obvious (`height_m`, `area_m2`, `azimuth_deg`).
- **Determinism.** Iterate in sorted id order. Stable sorts with explicit tie-breakers (id). No `set` iteration in output paths. Floats are not rounded inside the engine. Ten repeated runs must be byte-equal after JSON serialization.
- **Ranges.** Every index is clamped to 0–100 at the point it is computed, as PLANNING.md specifies.
- **Typed.** pyright strict. Results are frozen dataclasses with explicit fields, never loose dicts.
- **Settings, not literals.** Weights, thresholds, radii, crown sizes, waiting-point weights and risk thresholds come from `settings.py`. A numeric literal in scoring code is a review blocker (0, 1, 100 and unit conversions excepted).

## Domain rules that resolve gaps in PLANNING.md

- **Chunks.** Footpaths are 10 m chunks (the last chunk of a run may be shorter). A chunk is shaded at time *t* when its midpoint lies inside the union of shadows at *t*. Chunk PSS = 100 × shaded times ÷ 3. Block and area PSS are length-weighted means of chunk PSS.
- **Shadow sources.** Buildings: the footprint swept along the shadow vector of length `h / tan(altitude)` away from the sun (union of the footprint, its translate, and the quad swept by each edge, so concave footprints stay correct). Tree crowns: discs of the settings radius, raised to the settings crown height. Shade structures: their polygon at 3 m. Shade under a structure counts at every reference time.
- **Incremental rescoring.** A change touches only blocks and chunks within the settings radius (300 m for green terms, the longest shadow at 13:00 for shade). `STRtree` finds them; everything else keeps its baseline value object.
- **Ventilation.** After tree rows, recompute `c_canopy` and `r_eff` for every touched block whose street has H/W ≥ 1; a block VCI drop ≥ the settings threshold sets `ventilation_ok = False` and the `CANOPY_OBSTRUCTION` driver on that change.
- **Interactions are real.** Two changes that shade the same chunk count it once; green changes recompute `G_buf` and `d_green` from the merged geometry. Never sum single-site gains to get a portfolio score.
- **Greedy.** Sort single-site gain per rupee, tie-break by site id; add while within budget; rescore the portfolio after each addition and skip a site whose marginal gain is ≤ 0 or which fails ventilation.
- **Heights.** The engine uses `height_m` as given and never fills gaps; provenance is the pipeline's job.

## Tests required for a change here

- A golden test for any new or changed formula with the expected value worked out by hand in the test's docstring.
- The relevant direction test from PLANNING.md "Tests" as a hypothesis property.
- Determinism and range stay green on the tiny fixture.
