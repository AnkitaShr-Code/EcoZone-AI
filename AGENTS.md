# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, and any other agent that reads AGENTS.md) when working with code in this repository.

## Repository status

`pipeline/`, `engine/`, `api/`, `agents/`, `evals/`, and `infra/` are scaffolded (each holds a `README.md` describing what will live there) but have no application code yet. `app/` has a working UI shell on mock data (see `app/README.md`). This repo is the design/submission package for **NeuralNodes**' entry to the Google Cloud AI Builder Cup 2026 (theme: Sustainability & Social Impact), prototype due Oct 18, 2026. Treat every number, score, or benchmark in these docs as a planned target, not a measured result, unless a doc explicitly says it was measured.

Documentation lives in `docs/`. Read in this order when picking up work:

1. **README.md** (repo root) — product pitch, architecture one-liner, data sources, submission requirements.
2. **docs/ARCHITECTURE.md** — system shape, component ownership table, the two structural rules every change must preserve. Start here for anything touching more than one component.
3. **docs/PLANNING.md** — the source of truth: problem statement, scoring formulas (VCI, HEI, GCS, PSS, ACS, priority, risk label), agent/tool contracts, data pipeline, trust/grounding rules, build plan, locked decisions. Formulas are defined here once; other docs reference this file rather than repeating them.
4. **docs/DESIGN.md** — component-level design built on PLANNING.md: repository layout, per-component responsibilities (pipeline, engine, API, agents, front end, data stores, eval harness, deployment), key flows, performance budget, effort estimate, risks.
5. **docs/TASKS.md** — day-by-day checklist by lane (D = data/engine, A = agents/cloud, U = front end, All = whole team), gate criteria, and the cut order to apply if a gate slips.
6. **docs/PITCH_DECK_PLAN.md** — slide-by-slide plan for `Submission Template _ AI Builder Cup.pptx` / the working copy `NeuralNodes - AI Builder Cup Submission.pptx`.

## Core product concept (for context when code lands)

EcoZone AI treats a neighborhood as one cooling network (air paths, green patches/links, waiting points) with two modes sharing one engine and one map:

- **Repair** (lead mode): planner picks an area + rupee budget; Gemini proposes portfolios of five intervention types (street tree row, shade structure, depave and plant, pocket green, cool roof); a deterministic engine scores each against ACS (Area Cooling Score) and a ventilation constraint; Gemini refines for up to 3 rounds against a greedy baseline.
- **Protect** (second mode): planner previews a proposed building's effect on ventilation/heat/green/shade indices, then Gemini searches for alternative designs (options A/B/C) and can apply one envelope to a whole street (build-out).

Non-negotiable constraints that any future code must preserve (see docs/PLANNING.md "Grounding rules" and "What we will not claim"):

- **The scoring engine, not the LLM, computes every number.** Gemini/agents only call engine tools and report values that appear in that turn's tool results or planner input.
- **No temperature, wind-speed, or energy units** may appear in planner-facing output — the indices (VCI/HEI/GCS/PSS) are 0–100 heuristic screening scores, not physical measurements.
- **An output guard** (ADK `after_model_callback`) must reject ungrounded numbers and forbidden units before an answer reaches the planner; one regeneration, then a template fallback built from engine values.
- **AI-estimated values and planner-entered inputs are always visibly labeled**; costs come only from planner-entered unit costs, never presented as market prices.
- The system never approves, denies, or issues work orders — it is decision support only.

## Planned architecture (not yet implemented)

Full diagram and component-ownership table: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Summary:

```
React (deck.gl + MapLibre) ──REST──► FastAPI ──► engine (deterministic Python)
            │                                     ▲
            └──SSE──► ADK agents (Gemini on Vertex AI) ─┘ tools
                      output guard on every answer

offline pipeline (OSM, Open Buildings, Sentinel-2, WorldCover, Landsat, Open-Meteo)
      ──► BigQuery + Cloud Storage ──► loaded into the engine's memory at startup
sessions and plans ──► Firestore          one Cloud Run service serves UI and API
```

Repository layout, each owned by a lane (see [docs/DESIGN.md](docs/DESIGN.md) §2–3 for full detail; each directory also has its own `README.md`):

```
docs/       architecture, planning, design, tasks, deck plan
pipeline/   offline data job per city (D lane) — OSM extract, geometry, Earth Engine layers, wind/sun, baselines
engine/     deterministic scoring engine, pure Python, no network calls (D lane) — indices, interventions, rescoring, greedy baseline
api/        FastAPI routes + Pydantic schemas (A lane) — instant REST routes call the engine directly; agent runs go through SSE
agents/     ADK orchestrator + 4 sub-agents (Spatial Analyst, Repair Planner, Scenario Analyst, Planning Advisor), shared LoopAgent search, output guard (A lane)
app/        React + TypeScript + deck.gl/MapLibre front end (U lane)
evals/      pytest engine tests + agent eval scripts; results written to BigQuery and evals/REPORT.md
infra/      Dockerfile, Cloud Build config, deploy notes, IAM roles
```

Two structural rules to preserve when this code is written:

1. **Sliders never wait for AI.** Any REST route a UI control calls directly (rescore, simulate) must run in the deterministic engine only, in well under a second — Gemini is invoked only for explanations and the propose/score/refine search loops.
2. **One `rescore(area, changes)` routine serves both Repair and Protect build-out** — it is the single place that applies a list of `Change` objects and recomputes affected attributes/shadows/indices incrementally (STRtree-based radius queries), not two parallel implementations.

The Repair and Protect design-search loops are the *same* generic ADK `LoopAgent` (`agents/search.py`): an LLM Proposer emits candidates as structured JSON, a non-LLM Scorer calls the engine and drops invalid candidates, and a non-LLM Judge decides when to stop (max 3 rounds, or no candidate beats the best by a mode-specific threshold). Do not fork this into mode-specific loops.

## Working conventions

- **Front-end work follows [app/UI_RULES.md](app/UI_RULES.md)** (layout regions, step pattern, layer registry, tokens, copy, code structure). Change the rule there first if a change needs to break it.

- All geometry/CRS work is planned in UTM 43N (EPSG:32643) for metric accuracy; convert to WGS84 only at BigQuery `GEOGRAPHY` load time and for the map.
- Formulas (VCI, HEI, GCS, PSS, priority, ACS, risk label thresholds) live only in docs/PLANNING.md — if engine code is added, keep it as the single reference rather than duplicating constants/weights across docs or code comments.
- Gate dates and the cut order in docs/TASKS.md are load-bearing for scope decisions during this sprint (Oct 13–18, 2026) — if asked to add scope, check it against the cut order and the "never cut" list (Repair with all five interventions, the shade score, the Protect preview) before proceeding.
- No API keys or secrets are ever committed; planned auth is Application Default Credentials + a service account on Cloud Run.
