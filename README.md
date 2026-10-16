# EcoZone AI

**Repair and protect a city's cooling network.**

EcoZone AI helps a city cool the streets people already live and work on, and stops new buildings from undoing that work.

- **Repair:** a planner selects an area and sets a rupee budget. Gemini designs a mix of street trees, shade structures, depaving, pocket green and cool roofs. A deterministic engine scores every option, including how much footpath it shades at 1, 3 and 4 pm, and rejects options that would block the breeze.
- **Protect:** the planner previews what a proposed building does to ventilation, heat, green connectivity and shade. Gemini searches for better designs, and a build-out view shows the cumulative effect on a whole street.

Built by team **NeuralNodes** for the **Google Cloud AI Builder Cup 2026**, theme **Sustainability & Social Impact**. Prototype due Oct 18, 2026.

> **Status: design complete, build in progress.** Nothing below is a measured result. Evaluation numbers will be added to [Evaluation](#evaluation) only after the tests have been run.

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
3. Gemini proposes portfolios of interventions; the engine scores each one; Gemini refines for up to three rounds. A greedy baseline is computed alongside, and the better result is shown.
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
            └──SSE──► ADK agents (Gemini on Vertex AI) ─┘ tools
                      output guard on every answer

offline pipeline (OSM, Open Buildings, Sentinel-2, WorldCover, Landsat, Open-Meteo)
      ──► BigQuery + Cloud Storage ──► loaded into the engine's memory at startup
sessions and plans ──► Firestore          one Cloud Run service serves UI and API
```

- **Engine:** the only place a score is computed. Indices on a 0 to 100 scale: Ventilation Corridor Index, Heat Exposure Index (with a roof albedo term), Green Connectivity Score and Pedestrian Shade Score. Repair maximizes an exposure-weighted Area Cooling Score within the budget, with a quick-win share that must help this summer; dense tree rows are kept off deep, narrow streets, and no block may lose 10 or more ventilation points. Formulas: [docs/PLANNING.md](docs/PLANNING.md#scoring-engine).
- **Agents:** four ADK agents (Spatial Analyst, Repair Planner, Scenario Analyst, Planning Advisor), chosen by plain code from the API route. Both searches run as one ADK `LoopAgent`: Gemini proposes, and plain code scores the candidates and decides when to stop.
- **Trust:** an output guard rejects any number not found in the turn's tool results or planner inputs, and any temperature, wind or energy unit. AI-estimated values are labeled.
- **Data:** OpenStreetMap, Google Open Buildings 2.5D heights, Sentinel-2, ESA WorldCover, Open-Meteo wind, computed sun position; Landsat surface temperature is used only to validate the heat index. Google Maps tiles are not used.

Full component design: [docs/DESIGN.md](docs/DESIGN.md). System shape and component ownership: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Evaluation

Tests live in `evals/`. Results will be reported here once measured; no targets are claimed before then.

| Test | Checks |
| --- | --- |
| Determinism, range | Same inputs give the same scores; every index stays within 0 to 100 |
| Direction | Protect: more height or footprint never helps; more green never hurts. Repair: trees and shade never lower shade; depaving and cool roofs never raise heat |
| Shadow geometry | Known building height gives the expected shadow length and direction |
| Ventilation site rule | No tree row on a street with height-to-width 1 or more; such streets show as rejected |
| Budget and quick wins | Every shown portfolio is within budget and meets the quick-win share |
| Gemini vs greedy | Win, tie or loss per test area at the same budget |
| Grounding | No number outside tool results or planner input; no forbidden units |
| Design search | Options B and C come from scored candidates and follow their rules |
| Speed | Engine and search times |
| Heat check | Spearman correlation between the heat index and Landsat surface temperature on held-out blocks |

Limits stated openly: the indices are heuristic screening indicators and only the heat index is checked; the shade score is clear-sky geometry; roof albedo is a block-level estimate; parcels are road-network blocks; wind is one seasonal direction; trees take years to grow the canopy the plan assumes.

## Repository layout

Code directories are scaffolded (each holds a `README.md` describing what will live there and linking to its design section) but not yet implemented:

```
docs/       architecture, planning, design, tasks, deck plan
pipeline/   offline data job per city
engine/     deterministic scoring engine
api/        FastAPI routes
agents/     ADK agents, search loop, output guard
app/        React + TypeScript front end
evals/      tests and evaluation reports
infra/      Dockerfile, deploy config
```

## Running locally

Setup instructions will be added when the code lands. Planned requirements: Python 3.11+, Node 20+, a Google Cloud project with Vertex AI, BigQuery, Firestore and Cloud Storage enabled, and Earth Engine noncommercial access for the pipeline. Authentication is through Application Default Credentials and a service account; **no keys are committed to this repository.**

## Timeline

| Gate | Date | Passes when |
| --- | --- | --- |
| Engine on real data | Oct 14 | Baseline indices including shade exist for the frozen area; range and determinism tests pass |
| Both modes end to end | Oct 16 | Repair and Protect work locally |
| Feature freeze | Oct 17 | Deployed; evals run; demo area chosen |
| Submit | Oct 18 | Live link, repository, video and deck submitted |

## Submission

- Competition: [Google Cloud AI Builder Cup 2026](https://aibuildercup.com), theme **Sustainability & Social Impact**
- Deliverables: Cloud Run prototype (no login), public repository, demo video under 3 minutes, PDF deck

## License

[MIT](LICENSE)
