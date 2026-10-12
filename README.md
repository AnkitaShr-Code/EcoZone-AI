# EcoZone AI

**Climate impact preview for building proposals.**

EcoZone AI lets a city planner select a parcel, enter a proposed building, and see how ventilation, heat exposure and green connectivity change. Gemini then searches for better designs, and an area view shows what happens when every vacant parcel on a street is built out. The heat index is checked against satellite surface temperature.

Built by team **NeuralNodes** for the **Google Cloud AI Builder Cup 2026**, theme **Sustainability & Social Impact**. Prototype due Oct 18, 2026.

> **Status: planning complete, build in progress.** This README describes the designed system. Nothing below is a measured result. Evaluation numbers will be added to [Evaluation](#evaluation) only after the tests have been run.

## Why

Building proposals in fast-densifying cities such as Pune are checked against height limits, floor-area ratio and setbacks. None of these ask whether the building blocks the breeze that cools the blocks behind it, or replaces soil and trees with surfaces that hold heat. A fully legal building on the wrong plot can make a neighborhood hotter.

Outdoor workers, the elderly and children bear that exposure, and a cooling corridor that is built over cannot be restored. Detailed microclimate studies exist, but they are specialist work, so most proposals never get one. Cities ask "Can we build here?" and not "What happens to the neighborhood if we build here?"

Public evidence (full list in the [planning document](EcoZoning%20AI%20Climate%20Impact%20Preview%20for%20Building%20Proposals.md)):

- India recorded between 10,545 and 20,615 heat deaths from 2000 to 2020, depending on the counting agency ([Dialogue Earth via PreventionWeb](https://www.preventionweb.net/news/indian-cities-struggle-plan-heat-most-vulnerable-suffer), Apr 2026).
- About 57% of Indian districts are at high or very high heat risk (CEEW 2025, same article).
- In Pune, built-up area grew from 44.8% to 55.17% between 2012 and 2023, and heat islands appeared at four of six study sites ([Tiwari et al., 2025](https://archives.christuniversity.in/items/show/23402)).

## What it does

1. The planner selects a parcel on the map of the frozen demo area (Shivajinagar or Kothrud, chosen on day 1 by building-height coverage).
2. The planner enters a proposed building: height in floors, footprint %, green %, orientation.
3. The scoring engine computes baseline and proposed values for three 0–100 indices: **Ventilation Corridor Index (VCI)**, **Heat Exposure Index (HEI)** and **Green Connectivity Score (GCS)**.
4. Gemini explains the drivers, using only values returned by the engine.
5. Gemini searches for better designs and ranks three options.
6. The planner reads a short planning brief with the evidence and recommendation.
7. In **Area build-out**, one envelope is applied to every vacant parcel on a street and the whole area is rescored.

| Option | Optimizes | Rule |
| --- | --- | --- |
| A: Developer maximized | Floor area | The proposal as entered |
| B: Balanced | Climate score, keeping most floor area | Best candidate keeping at least a set share of A's floor area (planner-adjustable) |
| C: Climate optimized | Climate score | Best candidate above a minimum development floor, so the answer is never "do not build" |

Floor area = footprint % × floors, used as a simple proxy for development value.

### What it is not

- Not a computational fluid dynamics model. It does not predict degrees or wind speeds; the indices are screening indicators for comparing scenarios on the same parcel.
- Not a permit authority. It never approves or denies; it shows evidence and options.
- Not a new mandatory approval step. It fits large projects, development plan revisions, and making the case for a rule such as a height cap or minimum green share.

Professional tools such as [Autodesk Forma](https://www.autodesk.com/products/forma/environmental-impact-analysis) offer wind and microclimate analysis, but are paid and aimed at architects in early design. EcoZone AI is aimed at the official reviewing a proposal or plan, using free public data and a one-minute screening. It complements a detailed study on a large project; it does not replace one.

## Architecture

Four layers and one guard. Requests flow down from the planner app; every answer returns through the output guard.

```
Planner app (map, sliders, before/after, option cards, build-out view)
        │
Agent layer (Google Agent Development Kit, Gemini)
  Orchestrator ─┬─ Spatial Analyst   get_parcel_context, analyze_imagery
                ├─ Scenario Analyst  simulate_scenario, compare_scenarios, simulate_buildout
                └─ Planning Advisor  format_planning_brief
        │
Scoring engine (deterministic code, the only place a score is computed)
        │
Preprocessed data (BigQuery parcel table, Firestore sessions, image clips)
        │
Output guard ──► planner
```

| Store | Holds |
| --- | --- |
| BigQuery | Parcel table, geometry (GEOGRAPHY), attributes, baseline indices |
| Firestore | Scenarios, design-search candidates, imagery observations, conversation state |
| Cloud Run container | Engine, agents, frontend, demo image tiles |

### Scoring engine

Plain code over geometry and preprocessed layers. Gemini never computes a score.

$$VCI = 0.30\,W_a + 0.25\,C_o + 0.25\,O_b + 0.20\,P_g$$

$$HEI = 0.40\,I_s + 0.35\,(100 - G_c) + 0.25\,T_m$$

$$GCS = 0.5\,G_{buf} + 0.5\,L_{link}$$

| Index | Higher means | A proposal worsens it by |
| --- | --- | --- |
| VCI | Air can pass through the corridor | Lengthening the built run, raising height against street width, turning the building across the wind |
| HEI | More heat retention | Adding impervious surface, removing vegetation, adding building mass |
| GCS | More connected green cover nearby | Removing green cover, or isolating the remaining green from existing patches |

Term definitions, data sources and assumptions (3 m per floor, road-class street widths, remainder treated as paved) are in the [planning document](EcoZoning%20AI%20Climate%20Impact%20Preview%20for%20Building%20Proposals.md#scoring-engine).

**Risk label:** the worst change is the largest of the VCI drop, HEI rise and GCS drop. Under 10 points is LOW, 10–24 is MODERATE, 25 or more is HIGH. These thresholds are prototype settings.

> The indices are prototype composite indicators, not airflow or temperature measurements, and the weights are design heuristics. Only the heat index is checked against measurement; the other two are not validated.

### Area build-out

Applies one envelope (floors, footprint %, green %) to every candidate parcel in a selected area (capped at about 30 parcels) and rescores every parcel, neighbors included. Output: per-parcel change and risk label, area averages before and after, count of HIGH parcels, and how many existing blocks lose score. Floor-area and height limits are not in open data, so the envelope is planner input.

### Gemini's two jobs

**Design search** (propose, score, refine):

1. Gemini receives the proposal, its scores and the floor-area rule for option B.
2. It proposes four candidate designs within allowed ranges.
3. Each candidate is scored by `simulate_scenario`.
4. Candidates that break the floor-area rule are dropped; Gemini proposes a refined batch.
5. The loop stops after three rounds, or earlier when no candidate beats the best by more than 2 points.
6. Options B and C are selected from scored candidates only.

Levers: height, footprint %, green %, orientation (15° steps), green placement (scattered or connected corridor). Candidates may not exceed the proposal's height or footprint, or reduce its green share.

**Aerial imagery reading:** for the selected parcel, Gemini returns structured observations (tree-cover, paved and roof share, open spaces, confidence per field). Data layers stay primary. If imagery and a layer differ by more than 15 points, both values and a disagreement flag are shown. Where a layer is missing, the imagery estimate fills in, labeled **AI-estimated**.

### Trust rules

Enforced by code and tests:

- Every number comes from an engine tool result in the same turn.
- No physical units (°C, m/s, kWh) in planner-facing output.
- The agent never approves or denies a proposal.
- AI-estimated values always carry a label and confidence.
- An **output guard** rejects any number not present in that turn's tool results and any forbidden unit. A rejected answer is regenerated once; if it fails again, the planner sees a plain template built from engine values.
- Primary drivers (OBSTRUCTION, BUILT_RUN, IMPERVIOUS_GAIN, MASS_GAIN, GREEN_ISOLATED, …) are computed by the engine; Gemini only explains them.

### Tool contracts

| Tool | Inputs | Returns |
| --- | --- | --- |
| `get_parcel_context` | parcel id | Centroid, area, baseline indices, canyon axis, data-gap flags |
| `analyze_imagery` | parcel id | Structured observations with confidence per field |
| `simulate_scenario` | parcel id, floors, footprint %, green %, orientation, green placement | Baseline and proposed indices, deltas, driver tags, floor area, risk label |
| `compare_scenarios` | parcel id, scenario ids | Ranked table by climate score and floor area |
| `simulate_buildout` | area id or parcel ids, floors, footprint %, green % | Per-parcel deltas and labels, area averages, HIGH count, driver tags |
| `format_planning_brief` | parcel id, scenarios, selected option | Summary, risk label, recommendation, caveats |

## Data pipeline

All data is prepared once, offline, from open sources. The app reads preprocessed tables and never processes rasters while a planner waits.

| Layer | Source | Used for |
| --- | --- | --- |
| Buildings, roads, parks, water | OpenStreetMap (Overpass API) | Geometry, street width, canyon axis, distances |
| Building heights | [Google Open Buildings 2.5D Temporal](https://sites.research.google/gr/open-buildings/temporal) (2023) | Height and volume where OSM has no floors tag |
| Vegetation and built-up | Sentinel-2 SR (`COPERNICUS/S2_SR_HARMONIZED`) | Vegetation and built-up shares |
| Land cover | [ESA WorldCover](https://registry.opendata.aws/esa-worldcover-vito/index.html) v200 (2021) | Impervious and green shares |
| Prevailing wind | [Open-Meteo](https://open-meteo.com/) (ERA5) | Dominant seasonal wind direction |
| Surface temperature | Landsat 8/9 Collection 2 Level 2 | **Heat-index validation only** |
| Imagery for Gemini | Sentinel-2 true-color and vegetation false-color clips | `analyze_imagery` input |

Google Maps satellite tiles are deliberately not used: the Maps Platform terms bar using Maps content to train, test or validate AI models.

**Preprocessing job:** get Earth Engine noncommercial access → choose the demo area → extract OSM for a ~2.5 km × 2.5 km box → define parcels (road-network blocks with low building coverage or tagged vacant/open; OSM has no cadastral parcels) → add satellite layers in Earth Engine → get wind → compute per-parcel attributes → score and validate → export image clips → load to BigQuery.

**New city:** change the bounding box, wind direction and road-class width defaults, and rerun the same job. No engine or agent code changes. This claim is made for the demo area only until a second city is run.

**Fallback:** if the satellite steps miss the Oct 14 gate, use OSM land-use proxy indices and OSM-only heights with storey defaults, labeled as defaults.

## Evaluation

Tests live in `evals/`. Results will be reported here once measured; no targets are claimed before then.

| Test | Checks | Passes when |
| --- | --- | --- |
| Determinism | Same inputs, same scores | Ten repeated runs match exactly |
| Range | Indices within 0–100 | Holds on all test parcels (riverfront, dense interior, isolated corner) |
| Direction | More height/footprint never improves VCI or lowers HEI; more green never raises HEI or lowers GCS | Holds across a settings sweep per parcel |
| Grounding | Explanations contain only tool-result numbers and no forbidden units | Zero violations |
| Tool use | Agent fetches context and simulates before explaining | Success rate over ten parcels |
| Design search | B and C come from scored candidates; B keeps the floor-area share; C beats A on climate score | Holds per test parcel |
| Speed | Engine time per scenario, preview time, search time | Measured and reported |
| Heat check | Baseline HEI ranks blocks like measured surface temperature | Spearman correlation and block count on held-out blocks; no pass mark |

**Heat check method:** compute baseline HEI for every block → take each block's median Landsat surface temperature from cloud-free March–May scenes → split blocks randomly in half, tuning weights on the first half only → report Spearman correlation and block count on the second half. Two caveats travel with the number: surface temperature is not felt air temperature, and the index shares inputs with what drives surface temperature, so a good result shows ranking agreement, not that the weights are right.

### What we will not claim

Temperature, wind speed or energy figures in planner-facing output; fluid dynamics modeling; long-range forecasts; permit approvals or denials; results for any city other than the demo area.

### Known limits

- Indices are heuristic screening indicators; ventilation and green connectivity are not validated.
- OSM completeness varies; Open Buildings height accuracy has not been measured in India.
- Parcels are road-network blocks, not legal plots.
- Wind is a seasonal prevailing direction, not a wind field.

## Repository layout (planned)

```
.
├── README.md
├── EcoZoning AI Climate Impact Preview for Building Proposals.md   # full planning document
├── pipeline/    # offline data job: Overpass, Earth Engine, Open-Meteo, BigQuery load
├── engine/      # deterministic scoring engine (VCI, HEI, GCS, risk label, drivers)
├── agents/      # ADK orchestrator and agents, tool wrappers, output guard
├── app/         # frontend: map, sliders, before/after, option cards, build-out view
└── evals/       # determinism, range, direction, grounding, design search, heat check
```

This layout is a proposal and may change as the build lands.

## Timeline

| Gate | Date | Passes when |
| --- | --- | --- |
| Engine on real parcels | Oct 14 | Indices computed for real parcels, range and determinism tests pass, heat check has a first number |
| Full flow works | Oct 16 | Select, simulate, explain, design search and build-out work end to end locally |
| Feature freeze | Oct 17 | Deployed on Cloud Run, evals run, demo parcel chosen |
| Submit | Oct 18 | Live link, repository, video and deck submitted |

If time runs short: satellite indices fall back to OSM proxies, design search drops from three rounds to one, build-out runs on one prepared street, and UI polish is reduced.

## Running locally

Setup and run instructions will be added when the code lands. Planned requirements: Python, a Google Cloud project with Earth Engine (noncommercial), BigQuery and Firestore enabled, and a Gemini API key supplied through environment variables. **No keys are committed to this repository.**

## Submission

- Competition: [Google Cloud AI Builder Cup 2026](https://aibuildercup.com), theme **Sustainability & Social Impact**
- Deliverables: Cloud Run prototype (no login), public repository, demo video under 3 minutes, PDF deck
- Planning document: [EcoZoning AI Climate Impact Preview for Building Proposals.md](EcoZoning%20AI%20Climate%20Impact%20Preview%20for%20Building%20Proposals.md)

## License

To be decided before submission.
