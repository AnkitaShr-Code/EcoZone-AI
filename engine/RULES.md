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

## Public API

The only names `api`, `agents` and `pipeline` import, re-exported from `ecozone_engine/__init__.py`. Stubs with these signatures land in WP1 so other packages can build against them; the engine owner replaces the bodies without changing the signatures (a signature change is its own PR, agreed with the API and agents owner).

```python
load_bundle(path: Path) -> AreaModel
summary(area: AreaModel) -> AreaSummaryData
layer(area: AreaModel, name: LayerName) -> list[Feature]            # EPSG:32643; api converts to WGS84
hotspots(area: AreaModel, top: int) -> list[HotspotData]
single_site(area: AreaModel, site_id: str, unit_costs: UnitCosts) -> SingleSiteData
rescore(area: AreaModel, changes: Sequence[Change], unit_costs: UnitCosts) -> AreaResultData
greedy_baseline(area: AreaModel, budget_inr: float, unit_costs: UnitCosts, quick_win_share_pct: float) -> PortfolioData
shadows(area: AreaModel, time: ShadeTime, changes: Sequence[Change] = ()) -> list[Polygon]
compute_baselines(area: AreaModel) -> BaselineData                   # used by pipeline/baselines.py
```

All return types are frozen dataclasses in `model.py`; `api` and `agents` convert them to `contract` models in their `to_contract.py`.

**Errors.** Bad input raises a subclass of `EngineInputError` (`errors.py`): `UnknownSiteError`, `UnknownParcelError`, `QuantityOutOfRangeError`, `InvalidChangeError`. The message is shown to the planner. The API maps them to `SITE_NOT_FOUND`, `PARCEL_NOT_FOUND`, `QUANTITY_OUT_OF_RANGE` and `INVALID_CHANGE`; anything else is a bug and becomes `INTERNAL`.

**Building changes.** A Protect building is `Change(kind="building", site_id=<parcel id>, quantity=1, params=(("floors", f), ("footprint_pct", p), ("green_pct", g), ("orientation_deg", o)))`, params sorted by name.

**Layer properties.** `layer()` returns features whose `properties` use these keys (snake_case; the API camelCases them and converts geometry to WGS84). Block and parcel centroids are taken from the geometry by the API.

| Layer | Geometry | Properties |
| --- | --- | --- |
| `blocks` | Polygon | `area_m2`, `scores` (`Scores`), `priority`, `priority_class`, `built_form`, `wait_weight`, `drivers` (tuple of driver tags) |
| `segments` | LineString | `road_name`, `road_class`, `length_m`, `block_id`, `near_wait`, `shaded` (`ShadeByTime`) |
| `buildings` | Polygon | `height_m`, `height_source` |
| `wait_points` | Point | `kind`, `name`, `weight` |
| `parcels` | Polygon | `block_id`, `name`, `area_m2`, `road_name`, `road_width_m`, `street_bearing_deg`, `neighbour_height_m` |
| `sites` | LineString, Polygon or MultiPolygon | `kind`, `name`, `quantity`, `time_to_benefit` (`weeks`, `season` or `years`), `wait_point_id`, `h_w`, `points` (tree positions as x, y tuples, tree rows only) |

## Domain rules that resolve gaps in PLANNING.md

- **Chunks.** Footpaths are 10 m chunks (the last chunk of a run may be shorter). A chunk is shaded at time *t* when its midpoint lies inside the union of shadows at *t*. Chunk PSS = 100 × shaded times ÷ 3. Block and area PSS are length-weighted means of chunk PSS.
- **Shadow sources.** Buildings: the footprint swept along the shadow vector of length `h / tan(altitude)` away from the sun (union of the footprint, its translate, and the quad swept by each edge, so concave footprints stay correct). Tree crowns: discs of the settings radius, raised to the settings crown height. Shade structures: their polygon at 3 m. Shade under a structure counts at every reference time.
- **Incremental rescoring.** A change touches only blocks and chunks within the settings radius (300 m for green terms, the longest shadow at 13:00 for shade). `STRtree` finds them; everything else keeps its baseline value object.
- **Ventilation.** Tree rows never go on streets with H/W ≥ 1: the pipeline's site rule marks those candidates rejected (`CANOPY_OBSTRUCTION`), and the engine refuses them in `rescore`. Tree rows do not enter VCI (PLANNING.md, Oct 15 site rule; the old `c_canopy`/`r_eff` penalty is removed). `rescore` still sets `ventilation_ok = False` when any block's VCI drops by the settings threshold or more, which mainly applies to Protect buildings.
- **Risk label.** `rescore` measures the Protect risk on the block that contains each proposed building's parcel (that block's before and after `Scores`), never on the area-weighted scores. `AreaResultData.parcel_risk` has one `RiskInfo` per proposed parcel, sorted by parcel id; `risk` is the worst of them (ties by parcel id). Thresholds are in `settings.py`.
- **Interactions are real.** Two changes that shade the same chunk count it once; green changes recompute `G_buf` and `d_green` from the merged geometry. Never sum single-site gains to get a portfolio score.
- **Greedy.** First add quick wins (sites helping within weeks or a season) by single-site gain per rupee until their spend is at least the quick-win share; the last one may carry the spend past the share, and none is refused for doing so. Then add the rest the same way; tie-break by site id; add while within budget; rescore the portfolio after each addition and skip a site whose marginal gain is ≤ 0 or which fails ventilation. If the share cannot be reached within the budget, the plan is returned short and the caller flags it.
- **Heights.** The engine uses `height_m` as given and never fills gaps; provenance is the pipeline's job.

## Tests required for a change here

- A golden test for any new or changed formula with the expected value worked out by hand in the test's docstring.
- The relevant direction test from PLANNING.md "Tests" as a hypothesis property.
- Determinism and range stay green on the tiny fixture.
