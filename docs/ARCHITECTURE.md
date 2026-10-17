# EcoZone AI: architecture

Team NeuralNodes · Oct 15, 2026

How the product in [PLANNING.md](PLANNING.md) is built, in one place. This is the entry point for architecture; [DESIGN.md](DESIGN.md) carries the full per-component design (interfaces, data stores, flows, performance budget, effort estimate, risks), and the formulas themselves live only in [PLANNING.md](PLANNING.md#scoring-engine).

## Shape of the system

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
  │  FastAPI routes                     │   │  Agent layer    (Gemini on     │
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

Two rules shape everything, and any future code change must preserve them:

1. **Sliders never wait for AI.** Moving a slider or toggling an intervention calls a REST route that runs the engine in milliseconds. Gemini is called only for explanations and searches.
2. **The engine is the only place a number is made.** Agents call the engine through tools; the output guard checks every answer against the tool results.

## Components

| Component | Owns | Depends on |
| --- | --- | --- |
| `pipeline/` | Offline job per city: OSM extract, geometry, Earth Engine layers, wind/sun, baselines, validation, BigQuery/GCS load | Public data sources only; runs once per city, not in the request path |
| `engine/` | Deterministic scoring: `AreaModel`, shadows, indices (VCI/HEI/GCS/PSS), interventions, incremental area rescoring, priority/ACS, greedy baseline, drivers | Area bundle (GeoParquet from GCS) loaded at service startup; no network calls, no randomness |
| `api/` | FastAPI routes, Pydantic schemas, static serving of the React build, Firestore/BigQuery clients | `engine/` directly for REST routes; `agents/` for agent-run routes |
| `contract/` | Pydantic API models; `openapi.json`, from which the app's TypeScript types are generated | pydantic only |
| `agents/` | Code router, the Repair Planner and Scenario Analyst search roles, the writer, the shared search loop, the output guard (plain asyncio over `google-genai`, not ADK) | `engine/` through thin tool wrappers only — never computes a number itself |
| `app/` | React + TypeScript + deck.gl/MapLibre UI, SSE client, Repair/Protect panels | `api/` over REST and SSE |
| `evals/` | pytest engine tests, agent eval scripts, heat-check validation, `REPORT.md` | Reads from `engine/`, `agents/`, and BigQuery `eval_results` |
| `infra/` | Dockerfile, Cloud Build config, deploy notes, IAM roles | Builds `app/` and the Python services into one Cloud Run container |

Coding rules for every non-UI folder: [ENGINEERING_RULES.md](ENGINEERING_RULES.md) (Oct 15 decisions, stack, dependency direction, contract, testing, workflow). Front-end rules: [../app/UI_RULES.md](../app/UI_RULES.md).

Full component-level detail (interfaces, tool contracts, data store schemas, key flows, performance budget, effort estimate, risks) is in [DESIGN.md](DESIGN.md).

## References

| Topic | Where it lives |
| --- | --- |
| Problem, solution, scoring formulas, agent/tool contracts, trust rules, locked decisions | [PLANNING.md](PLANNING.md) |
| Component design, repository layout, data stores, flows, performance budget, effort, risks | [DESIGN.md](DESIGN.md) |
| Day-by-day task checklist, gates, cut order | [TASKS.md](TASKS.md) |
| Submission deck plan | [PITCH_DECK_PLAN.md](PITCH_DECK_PLAN.md) |
| Product pitch, evidence, submission requirements | [../README.md](../README.md) |
| Engineering rules (non-UI) | [ENGINEERING_RULES.md](ENGINEERING_RULES.md) and each folder's `RULES.md` |
| Agent-facing coding guidance | [../AGENTS.md](../AGENTS.md) |
