# EcoZone AI

**Repair and protect a city's cooling network.**

EcoZone AI helps a city cool the streets people already live and work on, and stops new buildings from undoing that work.

- **Repair:** a planner selects an area and sets a rupee budget. Gemini designs a mix of street trees, shade structures, depaving, pocket green and cool roofs. A deterministic engine scores every option, including how much footpath it shades at 1, 3 and 4 pm, and rejects options that would block the breeze.
- **Protect:** the planner previews what a proposed building does to ventilation, heat, green connectivity and shade. Gemini searches for better designs, and a build-out view shows the cumulative effect on a whole street.

Built by team **NeuralNodes** for the **Google Cloud AI Builder Cup 2026**, theme **Sustainability & Social Impact**. Prototype due Oct 18, 2026.

> **Status: working prototype, deployed.** Live: <https://ecozone-451227459430.asia-south1.run.app/> (no login). Both modes run on a real Deccan Gymkhana (Pune) bundle built from OpenStreetMap. Every measured number is in [evals/REPORT.md](evals/REPORT.md); this README quotes only what that report contains. Not built yet: saved plans and history, and Earth Engine data layers for the scores (Earth Engine is used only for the heat check below).

| Document | Contents |
| --- | --- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System shape, component ownership, the two rules every change must preserve |
| [docs/PLANNING.md](docs/PLANNING.md) | Problem, solution, scoring formulas, agents, data, trust, build plan, locked decisions |
| [docs/DESIGN.md](docs/DESIGN.md) | Components, interfaces, data stores, flows, performance and effort |
| [docs/TASKS.md](docs/TASKS.md) | Day-by-day checklist by lane |
| [docs/PITCH_DECK_PLAN.md](docs/PITCH_DECK_PLAN.md) | Slide-by-slide plan for the submission deck |
| [AGENTS.md](AGENTS.md) | Guidance for AI coding agents working in this repo |

## Why

Indian cities are getting hotter street by street. Outdoor workers, vendors, commuters, the elderly and children spend the hottest hours on footpaths, at bus stops and in school yards, often without shade. Cities have no quick way to decide where a limited budget for trees, shade or cool surfaces would help most. Meanwhile new buildings that follow every rule can still block the breeze and pave over the green that cools a neighborhood.

- India recorded between 10,545 and 20,615 heat deaths from 2000 to 2020, depending on the counting agency ([Dialogue Earth via PreventionWeb](https://www.preventionweb.net/news/indian-cities-struggle-plan-heat-most-vulnerable-suffer), Apr 2026).
- About 57% of Indian districts are at high or very high heat risk (CEEW 2025, same article).
- In Pune, built-up area grew from 44.8% to 55.17% between 2012 and 2023, and heat islands appeared at four of six study sites ([Tiwari et al., 2025](https://archives.christuniversity.in/items/show/23402)).

## How it works

The tool treats a neighborhood as one cooling network: air paths, green patches and links, and the places where people wait outdoors.

### Repair (lead mode)

1. Select an area. The map ranks blocks and footpaths by heat, missing afternoon shade, nearby waiting points (schools, hospitals, markets, bus stops) and dense low-rise built form.
2. Set a rupee budget, the share that must help this summer (quick wins), and check the unit costs (planner input).
3. Gemini proposes portfolios of interventions; the engine scores each one; Gemini refines for up to two rounds. A greedy baseline is computed alongside, and the better result is shown.
4. Read the plan: site, cost, why, waiting points covered, time to benefit, ventilation check, and rejected options with reasons.
5. Compare footpath shadows at 1, 3 and 4 pm before and after, and export a phased cooling plan with field check lists.

| Intervention | Where it helps | When the engine rejects or flags it |
| --- | --- | --- |
| Street tree row | Footpaths with little building shade, especially east–west streets | Deep narrow lanes, where canopy blocks the breeze |
| Shade structure | Within 30 m of a waiting point | — |
| Depave and plant | School yards, municipal parking, medians | — |
| Pocket green | Vacant or amenity plots that link existing green | Isolated plots score low |
| Cool roof | Dense low-rise blocks with dark roofs | — |

### Protect (second mode)

1. Select a parcel and enter a proposal: floors, footprint %, green %, orientation.
2. See baseline and proposed scores with a LOW, MODERATE or HIGH risk label, and Gemini's explanation of the drivers.
3. Gemini searches for better designs: A (as proposed), B (balanced, keeps most floor area), C (climate optimized above a minimum floor).
4. Build-out applies one envelope to every vacant parcel on a street and rescores the whole area.

### What it is not

Not a fluid dynamics or thermal comfort model: it never reports temperatures or wind speeds. Not a permit authority or work order. Costs come from planner unit costs, not market prices.

## Architecture

```
React (deck.gl + MapLibre) ──REST──► FastAPI ──► engine (deterministic Python)
            │                                     ▲
            └──SSE──► search loop (Gemini on Vertex AI) ─┘ tools
                      output guard on every answer

offline pipeline (OpenStreetMap, Open-Meteo wind, computed sun position)
      ──► GeoParquet bundle in Cloud Storage ──► loaded into the engine's memory at startup
                                          one Cloud Run service serves UI and API
```

- **Engine:** the only place a score is computed. Indices on a 0 to 100 scale: Ventilation Corridor Index, Heat Exposure Index (with a roof albedo term), Green Connectivity Score and Pedestrian Shade Score. Repair maximizes an exposure-weighted Area Cooling Score within the budget, with a quick-win share that must help this summer; dense tree rows are kept off deep, narrow streets, and no block may lose 10 or more ventilation points. Formulas: [docs/PLANNING.md](docs/PLANNING.md#scoring-engine).
- **Agents:** plain code picks the role from the API route. Both searches run as one propose, score, judge loop in plain `asyncio` over `google-genai` on Vertex AI (ADK is deliberately not used; see [docs/ENGINEERING_RULES.md](docs/ENGINEERING_RULES.md)): Gemini proposes, the engine scores every candidate, and plain code decides when to stop (two rounds at most). A greedy baseline always runs alongside. A writer role explains plans from engine values, with a template as fallback. Models: `gemini-3.5-flash` proposes and `gemini-3.8-flash` writes, on the `global` endpoint with low thinking.
- **Trust:** an output guard rejects any number not found in the turn's tool results or planner inputs, and any temperature, wind or energy unit. AI-estimated values are labeled.
- **Data in the shipped bundle:** OpenStreetMap (buildings, roads, footpaths, waiting points, green, water), Open-Meteo wind direction (ERA5, Mar to May), and computed sun position. Building heights come from OSM where tagged and otherwise from a block typology default (most Deccan buildings use the default, counted in the bundle's `meta.json`). Roof albedo is a labeled default. Open Buildings, Sentinel-2 and WorldCover are not used in this bundle. Landsat 8 and 9 surface temperature is used only to check the heat index, never to compute a score. Google Maps tiles are not used.

Full component design: [docs/DESIGN.md](docs/DESIGN.md). System shape and component ownership: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Evaluation

The evals live in `evals/` and run against the real engine and the Deccan v1 bundle (`uv run pytest evals -m "not live"`, about 4 minutes; `uv run python evals/report.py` regenerates [evals/REPORT.md](evals/REPORT.md)). The report carries the commit, bundle version and date of the run; numbers belong here only if it contains them. There are no pass marks for Gemini vs greedy or for the heat check.

| Test | Checks | Status in the report |
| --- | --- | --- |
| Determinism, range | Same inputs give the same scores; every index stays within 0 to 100 | Measured, pass |
| Direction | Protect: more height or footprint never helps; more green never hurts. Repair: trees and shade never lower shade; depaving and cool roofs never raise heat | Measured, pass |
| Ventilation guard | A plan or building that drops ventilation too far is flagged; the Protect risk label follows the parcel's own block | Measured, pass |
| Budget and quick wins | Every shown portfolio is within budget and meets the quick-win share | Measured, pass |
| Speed | Engine and search times | Measured (rescore of a plan about 64 ms; greedy at the 50 lakh budget about 19 s; bundle load about 0.6 s) |
| Gemini vs greedy | Win, tie or loss per test area at the same budget | Run with the offline rule proposer only; **live Gemini not yet reported** |
| Grounding, design search | No number outside tool results; B and C come from scored candidates | Covered by agent unit tests; **live runs not yet reported** |
| Heat check | Spearman correlation between the heat index and Landsat surface temperature on held-out blocks | **Measured, weak.** On the 33 held-out blocks the baseline heat index and Landsat surface temperature have a Spearman rho of +0.187 (permutation p 0.30, not significant); on all 65 blocks rho is +0.295 (p 0.015). The index ranks blocks in the same direction but the held-out agreement is weak, so we do not call it validated. The report lists the other indices and the caveats |

Shadow geometry and the ventilation site rule (no tree row where height-to-width is 1 or more) are covered by engine and pipeline unit tests.

Limits stated openly: the indices are heuristic screening indicators and the heat index agrees only weakly with Landsat surface temperature on held-out blocks (see the table) and the other indices are not validated; the shade score is clear-sky geometry; roof albedo is a block-level estimate; parcels are road-network blocks; wind is one seasonal direction; trees take years to grow the canopy the plan assumes.

## Repository layout

Each code directory has a `README.md` or `RULES.md` with its rules:

```
docs/       architecture, planning, design, tasks, deck plan
pipeline/   offline data job per city
engine/     deterministic scoring engine
api/        FastAPI routes
agents/     search loop, Gemini client, output guard, templates
app/        React + TypeScript front end
evals/      tests and evaluation reports
infra/      Dockerfile, deploy config
```

## Running locally

Requirements: [uv](https://docs.astral.sh/uv/) (installs Python 3.12 for you), Node 24, and Docker for the image. Google Cloud is needed only for Gemini (Vertex AI) and the bundle bucket; authentication is Application Default Credentials locally and a service account on Cloud Run, so **no keys are committed to this repository.**

```bash
uv sync                      # Python workspace: contract, engine, pipeline, agents, api
make check                   # ruff, pyright, import boundaries, pytest, plus the app's typecheck, lint and build
cd app && npm install && npm run dev            # the app alone at :5173, on mock data
uv run pipeline all --area deccan                # builds data/areas/deccan/v1 from OpenStreetMap (needs network)
mkdir -p data/bundles && cp -R data/areas/deccan/v1 data/bundles/deccan   # the API reads data/bundles/<area>/
ECOZONE_LLM=fake make api    # API at :8000/api; the offline proposer needs no cloud access (omit it to use Gemini on Vertex AI)
make app-http                # the app at :5173 on the API (VITE_API_MODE=http; /api is proxied)
uv run ecozone snapshot --area deccan           # refresh the app's mock files from the API
docker build -f infra/Dockerfile -t ecozone .   # the one Cloud Run image
```

Coding rules: [docs/ENGINEERING_RULES.md](docs/ENGINEERING_RULES.md) for everything outside `app/`, [app/UI_RULES.md](app/UI_RULES.md) for the app. Who builds what, and when: [docs/TASKS.md](docs/TASKS.md).

## Timeline

| Gate | Date | Passes when |
| --- | --- | --- |
| Engine on real data | Oct 14 (met Oct 17) | Baseline indices including shade exist for the frozen area; range and determinism tests pass |
| Both modes end to end | Oct 16 (met Oct 17) | Repair and Protect work locally and on Cloud Run |
| Feature freeze | Oct 17 | Deployed; evals run; demo area chosen |
| Submit | Oct 18 | Live link, repository, video and deck submitted |

## Submission

- Competition: [Google Cloud AI Builder Cup 2026](https://aibuildercup.com), theme **Sustainability & Social Impact**
- Deliverables: Cloud Run prototype (no login), public repository, demo video under 3 minutes, PDF deck

## License

[MIT](LICENSE)
