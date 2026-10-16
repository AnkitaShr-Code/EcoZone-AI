# EcoZone AI: component design

Team NeuralNodes · Oct 13, 2026

> **Oct 15:** decisions in [ENGINEERING_RULES.md](ENGINEERING_RULES.md#2-decisions-locked-on-oct-15) supersede this file where they differ (area bundle instead of BigQuery at startup, code routing instead of an LLM orchestrator, 10 m footpath chunks, a `contract/` package, one `rescore` route for Protect previews). Per-folder detail is in each folder's `RULES.md`; the sections below are updated to match.

How the system in [PLANNING.md](PLANNING.md) is built: the components, what each one owns, how they talk, where data lives, and how long each takes. The formulas live in PLANNING.md; this file does not repeat them.

## 1. Shape of the system

```
                         OFFLINE (once per city)
  OpenStreetMap ─┐
  Open Buildings ┤   pipeline/  ──────────────►  BigQuery  (ecozone_<city> dataset)
  Sentinel-2     ┤   (Python + Earth Engine)     Cloud Storage (area bundles, image clips,
  WorldCover     ┤                                              baseline shadows)
  Landsat (val.) ┤
  Open-Meteo     ┘

                         ONLINE (one Cloud Run service)
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  React app (static build, served by the same service)                   │
  │     deck.gl layers on MapLibre · Repair / Protect panels · SSE client   │
  └──────────────┬──────────────────────────────────────┬───────────────────┘
                 │ REST (instant, no AI)                 │ SSE (agent runs)
  ┌──────────────▼──────────────────────┐   ┌────────────▼────────────────────┐
  │  FastAPI routes                     │   │  ADK agent layer (Gemini on     │
  │  /areas /parcels /interventions     │   │  Vertex AI)                     │
  │  /shadows /buildout                 │   │  Code router → 4 agents         │
  └──────────────┬──────────────────────┘   │  LoopAgent searches             │
                 │                          │  Output guard (callback)        │
                 │                          └────────────┬────────────────────┘
                 │                tools call the engine   │
  ┌──────────────▼────────────────────────────────────────▼──────────────────┐
  │  engine/  (pure Python, deterministic)                                   │
  │  AreaModel in memory · shadows · VCI HEI GCS PSS · interventions ·       │
  │  area rescoring · priority · ACS · greedy baseline · drivers             │
  └──────────────┬───────────────────────────────────────────────────────────┘
                 │ load area bundle at startup        api writes
     Cloud Storage: area bundle (GeoParquet)      Firestore (sessions, plans,
     BigQuery: analytics copy, runs, evals        portfolios, observations)
```

Two rules shape everything:

1. **Sliders never wait for AI.** Moving a slider or toggling an intervention calls a REST route that runs the engine in milliseconds. Gemini is called only for explanations and searches.
2. **The engine is the only place a number is made.** Agents call the engine through tools; the output guard checks every answer against the tool results.

## 2. Repository layout

```
pipeline/          offline job, run once per city
  config/pune.yaml   bbox, CRS (EPSG:32643), wind season, reference date, road widths
  osm_extract.py     buildings, roads, sidewalks, green, water, waiting points, public land
  geometry.py        blocks (polygonize), footpath runs and 10 m chunks, road widths
  classify.py        Protect parcels, Repair candidate sites, built-form class
  ee_layers.py       Earth Engine: heights, S2 shares, roof albedo, WorldCover, LST, clips
  wind.py            Open-Meteo prevailing direction
  sun.py             sun altitude and azimuth at 13:00, 15:00, 16:00 IST on 15 April
  attributes.py      per-block and per-segment attributes
  baselines.py       baseline shadows, VCI, HEI, GCS, PSS, priority, ACS
  validate.py        heat check against Landsat (held-out half)
  load.py            BigQuery tables, GCS bundles
engine/            pure Python package, no cloud imports
  area_model.py      AreaModel: GeoDataFrames + STRtree indexes for one area
  shadows.py         building, crown and structure shadow polygons
  indices.py         vci(), hei(), gcs(), pss()
  interventions.py   apply_tree_row(), apply_shade(), apply_depave(), apply_pocket_green(), apply_cool_roof()
  proposals.py       apply_building() for Protect
  rescoring.py       rescore(area, changes) for Repair and build-out
  priority.py        priority(), acs()
  drivers.py         driver tags
  greedy.py          greedy_baseline()
  costs.py           portfolio cost from unit costs
api/               FastAPI app
  main.py            routes, static file serving, startup area load
  schemas.py         Pydantic request and response models
  store.py           Firestore and BigQuery clients
agents/            ADK
  runner.py          code routing by task (no LLM orchestrator)
  spatial.py repair.py scenario.py advisor.py
  tools.py           thin wrappers: tool → engine call → JSON result
  search.py          generic LoopAgent search used by both modes
  guard.py           after-model callback: number and unit check
  prompts/           one prompt file per agent
app/               React + TypeScript (Vite)
  src/map/           MapView, layers/*.ts
  src/repair/        BudgetPanel, SearchProgress, PlanTable, ShadowCompare
  src/protect/       ProposalPanel, BeforeAfter, OptionCards, BuildoutPanel
  src/shared/        ModeSwitch, Badges, ExplainPanel, BriefView, api.ts, sse.ts, store.ts
evals/             pytest engine tests, agent eval scripts, results → BigQuery + REPORT.md
infra/             Dockerfile, cloudbuild.yaml, deploy notes, IAM roles
```

## 3. Components

### C1. Pipeline (offline)

| Item | Detail |
| --- | --- |
| Runs | Locally or as a Cloud Run Job; idempotent per city config |
| Libraries | osmnx, geopandas, shapely 2, pyproj, earthengine-api, pvlib, google-cloud-bigquery |
| CRS | All geometry in UTM 43N (EPSG:32643) for metres; converted to WGS84 only when loading to BigQuery GEOGRAPHY and for the map |
| Footpaths | OSM `footway=sidewalk` where present; otherwise both road edges via `offset_curve(±width/2)`, buffered by 1.5 m, split into 10 m chunks; each chunk keeps its bearing, side, adjacent block and street H/W |
| Repair candidate sites | Tree rows: segments on road classes wide enough for a planting strip. Shade: points within 30 m of waiting points. Depave: `amenity=school` grounds, `amenity=parking` surface lots, medians, traffic islands. Pocket green: vacant or amenity plots. Cool roofs: buildings in dense low-rise blocks. Each site gets a quantity range and a geometry id |
| Earth Engine | One script per layer, `reduceRegions` over blocks and building footprints, exported as tables; roof albedo from a published Sentinel-2 broadband albedo coefficient set (chosen and cited on day 1) |
| Baseline shadows | Computed here for the three reference times and saved to GCS as GeoJSON, so the map loads them without computing |
| Output | BigQuery dataset `ecozone_pune`; GCS `gs://ecozone-<project>/pune/` |

### C2. Scoring engine

Pure Python, no network calls, deterministic. Everything else depends on it, so it is built and tested first.

```python
@dataclass(frozen=True)
class Change:              # one intervention or one proposed building
    kind: Literal["tree_row", "shade", "depave", "pocket_green", "cool_roof", "building"]
    site_id: str
    quantity: float        # trees, m², or a building's floors
    params: dict           # crown size, albedo after coating, footprint %, green % ...

@dataclass
class AreaResult:
    acs_before: float; acs_after: float
    blocks: list[BlockDelta]           # VCI, HEI, GCS, PSS before/after, drivers
    segments: list[SegmentDelta]       # PSS before/after per footpath segment
    ventilation_ok: bool; worst_vci_drop: float
    wait_points_covered: int; cost_inr: float; drivers: list[str]

def rescore(area: AreaModel, changes: list[Change], unit_costs: dict) -> AreaResult: ...
```

| Concern | Design |
| --- | --- |
| Area in memory | `AreaModel` holds one area's buildings, blocks, segments, sites and baselines, loaded from the GeoParquet area bundle on GCS at service start (the Deccan box has about 630 buildings) |
| Shadows | Building shadow = convex hull of the footprint and the footprint translated by `h / tan(altitude)` away from the sun's azimuth; crowns are circles translated by crown height; shade structures are polygons at 3 m. Shapely 2 vectorized operations |
| Incremental rescoring | A change only touches blocks and segments within a radius (300 m for green terms, the longest shadow for PSS). STRtree finds them; the rest keep their baseline. Target: under 200 ms per portfolio |
| Interventions | Each `apply_*` returns the attribute deltas and new shadow geometry for its site; `rescore` merges them and recomputes indices only where touched |
| Ventilation | Site rule at classification: tree-row candidates on streets with height-to-width 1 or more are marked rejected (CANOPY_OBSTRUCTION) and never enter a plan. `rescore` still sets `ventilation_ok = False` when any block's VCI drops by 10 or more (mainly Protect buildings) |
| Greedy baseline | Score each candidate site alone; fill the quick-win share with quick wins by ACS gain per rupee, then add the rest by gain per rupee while within budget |
| Determinism | No randomness; stable sort keys; float rounding only at the API edge |

### C3. API service (FastAPI)

Instant, deterministic routes used directly by the UI, and the agent run routes.

| Route | Purpose |
| --- | --- |
| `GET /api/areas/{area}` | Metadata, baseline area indices, data-gap flags |
| `GET /api/areas/{area}/layers/{name}` | GeoJSON layers (blocks, segments, waiting points, sites, buildings); large ones redirect to GCS |
| `GET /api/areas/{area}/hotspots?top=20` | Priority ranking with drivers |
| `GET /api/areas/{area}/sites?types=tree_row,shade` | Candidate sites with cost at current unit costs |
| `POST /api/areas/{area}/rescore` | Body: list of changes and unit costs. Returns `AreaResult`. Used for manual Repair edits, Protect previews (a `building` change) and build-out. Full route list: [../api/RULES.md](../api/RULES.md#routes) |
| `GET /api/areas/{area}/shadows?t=15:00&portfolio={id}` | Shadow polygons, baseline or with a portfolio |
| `POST /api/areas/{area}/greedy` | Greedy baseline for a budget |
| `POST /api/areas/{area}/buildout` | Build-out for an envelope |
| `POST /api/agent/runs` | Start an agent run (`mode`, `task`, `session_id`, context); returns `run_id` |
| `GET /api/agent/runs/{run_id}/events` | Server-sent events: round started, candidate scored, guard result, final answer |
| `GET /api/plans/{id}/brief` | Cooling plan or planning brief as HTML for printing |

The same container serves the React build as static files, so there is one URL, no CORS and no proxy timeouts on long SSE streams.

### C4. Agent layer (ADK on Vertex AI Gemini)

| Agent | ADK type | Tools | Notes |
| --- | --- | --- | --- |
| Router | Plain code (`runner.py`) | — | Picks the agent by API route; no LLM hop |
| Spatial Analyst | `LlmAgent` | get_area_context, get_parcel_context, analyze_imagery | Imagery is multimodal input (image clips from GCS) |
| Repair Planner | `LlmAgent` + search loop | rank_hotspots, list_candidate_sites, simulate_interventions, greedy_baseline | Runs the portfolio search |
| Scenario Analyst | `LlmAgent` + search loop | simulate_scenario, compare_scenarios, simulate_buildout | Runs the design search |
| Planning Advisor | `LlmAgent` | format_cooling_plan, format_planning_brief | Writes explanations and briefs |

**One search loop, two uses.** `search.py` builds an ADK `LoopAgent` with `max_iterations=3` and three steps:

1. **Proposer** (`LlmAgent`, Gemini): reads the best results so far from session state, proposes four candidates as structured JSON (portfolios for Repair, designs for Protect).
2. **Scorer** (custom `BaseAgent`, no LLM): calls the engine for each candidate, drops invalid ones (over budget, below the quick-win share, ventilation fail, floor-area rule), writes scores to state, emits one progress event per candidate.
3. **Judge** (custom `BaseAgent`, no LLM): stops the loop (escalate) when no candidate beats the best by the threshold (0.5 ACS points for Repair, 2 points for Protect).

The scorer and judge are plain code, so the loop's control flow is deterministic and only the proposals come from Gemini.

| Concern | Design |
| --- | --- |
| Model | Gemini on Vertex AI through a service account; exact model name confirmed against the Vertex AI model list on day 1 |
| Structured output | Proposer and imagery outputs use response schemas, so candidates parse without regexes |
| Output guard | ADK `after_model_callback`: extracts every number from the text, checks it against numbers in this turn's tool results and planner inputs (with rounding tolerance), and rejects forbidden units (°C, m/s, kWh). One regeneration, then a template filled from engine values |
| Sessions | ADK in-memory session service per instance, Cloud Run session affinity on; finished portfolios, plans and observations are written to Firestore so nothing is lost on restart |
| Progress | Scorer and judge events are forwarded to the SSE stream, which drives the live search animation |
| Cost control | Proposer sees compact JSON summaries, not geometry; at most 3 rounds × 1 Gemini call per search |

### C5. Front end (React + TypeScript)

| Part | Design |
| --- | --- |
| Stack | Vite, React, TypeScript, deck.gl via `MapboxOverlay` on MapLibre GL, Zustand for state, TanStack Query for REST |
| Basemap | A free vector style that needs no key (OpenFreeMap or similar; check its terms on day 1). No Google Maps tiles |
| Layers | `GeoJsonLayer` priority blocks (colors plus text classes); `PolygonLayer` extruded buildings from heights; `PolygonLayer` shadows for the selected time; `PathLayer` footpaths colored by PSS; `ScatterplotLayer` waiting points; `IconLayer` interventions; `GeoJsonLayer` candidate parcels |
| Repair screen | Budget and unit-cost panel (planner-input badges) → "Draft cooling plan" → SearchProgress (rounds, candidates as they are scored, greedy shown alongside) → PlanTable (site, type, cost, drivers, wait points, time to benefit, ventilation) with rejected rows → ShadowCompare (time slider, before and after) → BriefView |
| Protect screen | ProposalPanel sliders call `/simulate` on change → BeforeAfter bars with arrows and numbers → Explain → OptionCards A, B, C with "Apply" → BuildoutPanel |
| Accessibility | Arrows and text with every color; keyboard-operable controls; legends in words; focusable map features have list equivalents (the plan table) |

### C6. Data stores

**BigQuery dataset `ecozone_<city>`**

| Table | Key columns |
| --- | --- |
| `buildings` | building_id, geom GEOGRAPHY, height_m, height_source (osm, open_buildings, default), roof_albedo, block_id |
| `blocks` | block_id, geom, area_m2, coverage, built_form, I_s, G_c, G_buf, d_green, d_water, H_W, canyon_axis, L_built, V, roof_albedo, VCI, HEI, GCS, PSS, priority, E, V_w, lst_median (validation only), split (tune or test) |
| `segments` | segment_id, geom, block_id, bearing, side, length_m, road_class, H_W, pss_1300, pss_1500, pss_1600, PSS |
| `wait_points` | point_id, geom, kind, weight |
| `parcels` | parcel_id, geom, block_id, coverage, vacant_tag |
| `sites` | site_id, geom, kind, quantity_min, quantity_max, rules_passed |
| `area_meta` | area_id, bbox, wind_dir, sun table, V_ref, data-gap counts, pipeline version |
| `runs` | run_id, mode, area_id, budget, portfolio JSON, acs_gain, cost, greedy_gain, latency_ms, guard_violations, created_at |
| `eval_results` | test, area or parcel, result, value, run_at, commit |

**Firestore**

| Collection | Holds |
| --- | --- |
| `sessions/{id}` | Mode, area, planner inputs, unit costs |
| `sessions/{id}/portfolios/{id}` | Changes, AreaResult summary, round, source (gemini or greedy) |
| `sessions/{id}/scenarios/{id}` | Protect proposals and results |
| `sessions/{id}/observations/{id}` | Imagery observations with confidence |
| `plans/{id}` | Final cooling plan or planning brief |

**Cloud Storage** `gs://ecozone-<project>/<city>/`: `layers/*.geojson`, `shadows/baseline_{1300,1500,1600}.geojson`, `clips/{site_id}_{rgb,fcc}.png`, `briefs/`.

### C7. Evaluation harness

| Part | Design |
| --- | --- |
| Engine tests | pytest: determinism, range, direction (both modes), shadow geometry, ventilation site rule, budget and quick-win share |
| Agent evals | Scripted runs over fixed areas and parcels: grounding violations, tool-use order, design search rules, Gemini vs greedy |
| Heat check | `pipeline/validate.py`, held-out half, Spearman plus scatter PNG |
| Output | Rows in `eval_results`, and `evals/REPORT.md` generated for the README and deck |

### C8. Deployment and operations

| Item | Design |
| --- | --- |
| Build | One Dockerfile: build the React app, copy into the Python image; Cloud Build or GitHub Actions on push to `main` |
| Run | One Cloud Run service; min instances 1 during judging to avoid cold starts; session affinity on; area loaded at startup |
| Identity | Service account with BigQuery Data Viewer and Job User, Firestore User, Storage Object Viewer, Vertex AI User. No API keys anywhere |
| Earth Engine | Runs offline in the pipeline under the noncommercial project, not in the live service |
| Observability | Cloud Logging with run_id on every line; `runs` table in BigQuery for latency and guard statistics |
| Cost guard | Billing budget alert; search capped at 3 Gemini calls; min instances back to 0 after judging |

## 4. Key flows

**Repair: draft a cooling plan**

1. UI loads the area: layers from GCS, `GET /hotspots`, baseline shadows.
2. Planner sets budget, quick-win share and unit costs; UI calls `POST /agent/runs` with mode `repair`.
3. Router → Spatial Analyst (`get_area_context`) → Repair Planner (`rank_hotspots`, `list_candidate_sites`, `greedy_baseline`).
4. Search loop: up to 3 rounds of propose (Gemini) → score (engine) → judge. Each scored candidate streams to the UI.
5. Planning Advisor writes the plan from the best portfolio's `AreaResult`; the guard checks it.
6. Plan saved to Firestore, run logged to BigQuery; UI shows the plan, the shadows (`GET /shadows?portfolio=`) and the brief.

**Repair: manual edit.** The planner removes a tree row from the plan → `POST /rescore` → new scores in under a second, no Gemini call.

**Protect: preview.** Slider change → `POST /parcels/{id}/simulate` → bars update. "Explain" and "Find better designs" start agent runs the same way as Repair.

## 5. Performance budget

| Step | Target |
| --- | --- |
| Area load at service start | Under 10 s |
| `rescore` for one portfolio | Under 200 ms |
| Protect `simulate` | Under 100 ms |
| Shadows for one time step with a portfolio | Under 500 ms |
| Full Repair search (3 rounds) | Under 60 s; returns best so far at a time limit |
| Map first render | Under 3 s on a laptop |

These are targets to measure, not claims.

## 6. Effort estimate

Hours for builders comfortable with the stack, including debugging time.

| Lane | Component | Hours |
| --- | --- | --- |
| D | OSM extract, blocks, footpath segments | 6 |
| D | Classification: parcels, sites, built form, waiting points | 4 |
| D | Wind and sun | 2 |
| D | Attributes and baselines | 7 |
| D | Shadows and PSS | 7 |
| D | Indices, priority, ACS, drivers, risk label | 5 |
| D | Interventions, proposals, area rescoring | 8 |
| D | Greedy baseline | 2 |
| D | Engine tests | 4 |
| **D total** | | **45** |
| A | Earth Engine layers (heights, Sentinel-2, albedo, WorldCover, Landsat, clips) | 8 |
| A | BigQuery schema and loader | 3 |
| A | FastAPI routes and area loading | 5 |
| A | ADK agents and tool wrappers | 6 |
| A | Generic search loop (both modes) | 6 |
| A | Output guard | 3 |
| A | Imagery reading and field check lists | 3 |
| A | Firestore persistence | 2 |
| A | Docker, Cloud Run, IAM | 4 |
| A | Agent evals | 3 |
| **A total** | | **43** |
| U | Scaffold, basemap, deck.gl layers | 8 |
| U | Repair panels, live search, plan table | 8 |
| U | Shadow time slider and before/after | 4 |
| U | Protect panels, options, build-out | 8 |
| U | SSE client, brief view | 3 |
| U | Accessibility and polish | 2 |
| **U total** | | **33** |
| All | Video, deck, README, submission | 12 |
| **Total** | | **about 133** |

About 133 hours sits at the top of the 100 to 130 range, so the cut order in PLANNING.md will probably trigger at least once. The U lane has the most slack and should pick up the brief view, the deck diagrams and the video edit.

Optimizations already built into this design:

- One search loop serves both modes.
- Baseline shadows are computed offline, so the map never waits for them.
- One container serves the UI and the API.
- The engine is incremental, so every Repair and build-out change is cheap.

## 7. Risks

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Earth Engine approval late | No heights, albedo or heat check | Fallback at Gate 1: OSM heights with storey defaults, default albedo, heat check to future work |
| OSM sidewalks and waiting points sparse in the chosen box | Weak PSS and priority | Count them on day 1 when choosing the box; derived footpaths are labeled |
| Footpath derivation messy at junctions | Odd segments and shadows | Clip segments 10 m back from junctions; exclude very short segments |
| Gemini rarely beats greedy | Weak Gen AI story | Report it honestly; Gemini still explains and writes field check lists; tune the proposer prompt toward site interactions |
| Search too slow | Video drags | Time limit with best-so-far; one round in the worst case |
| Integration late | Nothing works end to end | Empty service deployed on Oct 13; API contracts (Pydantic schemas) fixed on Oct 13 so lanes work in parallel against stubs |
