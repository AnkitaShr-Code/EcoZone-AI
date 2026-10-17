# Engineering rules

The contract for everything outside `app/` (which has its own [UI_RULES.md](../app/UI_RULES.md)): `contract/`, `pipeline/`, `engine/`, `api/`, `agents/`, `evals/`, `infra/`. Read this before writing code in any of them, then read the `RULES.md` in the folder you are touching. If a change needs to break a rule, change the rule here first, in the same PR, with the reason.

Product and formulas: [PLANNING.md](PLANNING.md). System shape: [ARCHITECTURE.md](ARCHITECTURE.md). Component design: [DESIGN.md](DESIGN.md).

## 1. Principles

1. **The engine is the only place a number is made.** Pipeline baselines, API responses, agent tool results, mock fixtures and eval values all come from `engine/` functions. Nothing else re-implements a formula, not even "just for the baseline".
2. **Sliders never wait for AI.** Every route the UI calls on a control change runs the engine only and stays inside the performance budget (§8). Gemini runs only behind the search and explain routes.
3. **One `rescore(area, changes)`.** Repair portfolios, manual plan edits, Protect previews, design-search candidates and build-out all go through it. There is no second scoring path, and no precomputed lookup that stands in for it.
4. **Contract first.** The Pydantic models in `contract/` are the API. The TypeScript types, the OpenAPI file and the mock fixtures are generated from or validated against them. A field exists only if it is in `contract/`.
5. **Deterministic by construction.** Same bundle + same inputs gives byte-identical engine output. No randomness, no wall-clock, no dict-order or set-order dependence, no network inside the engine.
6. **Provenance travels with the value.** Every value that is a default, planner input or AI estimate carries a source field from the pipeline to the screen (`height_source`, `unit_cost.source`, `provenance`). Nothing silently fills a gap.
7. **Offline data, online scoring.** Network fetches and raster work happen only in `pipeline/`. The live service reads one immutable area bundle and never calls OSM, Earth Engine or Open-Meteo.
8. **No secrets anywhere.** Application Default Credentials locally, the Cloud Run service account in production, Workload Identity Federation in CI. No API keys or JSON key files, in code, env files or history.

## 2. Decisions locked on Oct 15

These override older wording in DESIGN.md and PLANNING.md where they differ (both are updated to match).

| Decision | Choice | Why |
| --- | --- | --- |
| Demo area | Deccan Gymkhana – Fergusson College box (`deccan`, bbox 73.838,18.5165 → 73.848,18.5245), frozen | The UI is already built on it; small enough for fast rescoring |
| Earth Engine | Pending. The OSM-only path is built first; EE layers plug in as an optional pipeline step if approval lands | Don't block the engine on an approval |
| Building heights | OSM `height` → OSM `building:levels` × 3 m → Open Buildings 2.5D (if EE) → typology default by building tag and footprint size, each with `height_source` | 98% of Deccan buildings have no OSM height; a flat 9 m makes every shadow the same |
| Footpaths | 10 m chunks; each chunk has a shaded/unshaded flag per reference time; PSS is the length-weighted shaded share | Matches the UI contract; see [engine/RULES.md](../engine/RULES.md) |
| Area load | Pipeline writes a versioned GeoParquet **area bundle** to GCS; the service loads it at startup. BigQuery gets a copy for analytics, ST_ queries, `runs` and `eval_results`, but is not in the request path | Fast startup, works offline and in tests |
| Persistence | `Store` protocol with an in-memory implementation (local, tests) and a Firestore one (prod) | Sessions and plans survive restarts without making every test need cloud |
| API contract | Pydantic in `contract/` → `openapi.json` → `openapi-typescript` for the app | One source; generated TS can't drift |
| Protect preview | Discrete slider levels kept; every preview is a live `rescore` with a `building` change. The per-parcel shade lookup leaves the contract | One scoring path |
| Agent routing | The API chooses the agent by route (deterministic). The search loop (Proposer → Scorer → Judge) and the writer are plain asyncio code calling Gemini through `google-genai` on Vertex AI; **not ADK** (changed in WP7, reasons below). No LLM orchestrator hop | The UI never sends free-form chat; routing by LLM adds latency and nondeterminism. ADK 2.12 deprecates `LoopAgent` for `Workflow`, which cannot yet be a sub-agent; it adds about 35 locked packages and downgrades fastapi, opentelemetry and websockets in the shared lock; and the loop must emit an event per candidate, keep the best result on cancellation and call the engine in threads, which is simpler as code than as session state. A fake `BaseLlm` did run a loop offline (checked), so an ADK-backed `ModelClient` can be added later without touching the loop |
| Models | Gemini Flash tier for the search proposer, Pro tier for explanations and briefs. Exact Vertex model IDs set by env, verified against the Vertex model list before first use | Search speed vs prose quality |
| Python packaging | uv workspace, Python 3.12, one package per folder, import boundaries enforced by import-linter | The engine physically can't import a cloud SDK |
| Workflow | Short-lived branches, PR to `main`, CI must pass, squash merge; `main` deploys to Cloud Run | Several people and agents committing at once |
| Mock data | Once the engine runs, `app/public/mock/<area>/` is a **snapshot of real engine responses** written by `api` (`uv run ecozone snapshot`). `app/scripts/build-mock-data.mjs` is retired at that point | Mock mode stays for offline UI work, but its numbers become real |
| Scope cuts | None taken now; the cut order in PLANNING.md applies only at a failed gate | Team decision |
| Default unit costs | Researched from public schedules of rates/tenders, stored with a citation per row, always labeled planner input | Never presented as market prices |

## 3. Stack baseline

Pinned in `uv.lock`; upgrade only in a PR that does nothing else.

| Concern | Library | Used in |
| --- | --- | --- |
| Runtime | Python 3.12 (not 3.13+, for geospatial wheels and ADK) | all |
| Package and env manager | `uv` (workspace, lockfile, `uv run`) | all |
| Geometry | `shapely` ≥ 2 (vectorized ops, `STRtree`), `pyproj` | engine, pipeline |
| Tables | `geopandas`, `pandas`, `numpy`, `pyarrow` (GeoParquet) | engine (load only), pipeline |
| OSM | `osmnx` (Overpass), raw responses cached to disk | pipeline |
| Sun | `pvlib` (sun altitude and azimuth) | pipeline |
| Wind | Open-Meteo historical API via `httpx` | pipeline |
| Earth Engine (optional step) | `earthengine-api` | pipeline |
| API models | `pydantic` v2, `pydantic-settings` | contract, api |
| HTTP | `fastapi`, `uvicorn`, `sse-starlette` | api |
| Agents | `google-genai` (Vertex AI backend), `pydantic-settings` | agents |
| Google Cloud | `google-cloud-storage`, `google-cloud-firestore`, `google-cloud-bigquery` | api (store), pipeline (load) |
| Tests | `pytest`, `hypothesis` (property tests), `pytest-benchmark` (speed) | all |
| Lint and format | `ruff` (lint + format) | all |
| Types | `pyright`: strict for `engine` and `contract`, standard elsewhere | all |
| Boundaries | `import-linter` | all |
| TS generation | `openapi-typescript` 7.13, run through pinned `npx` because it requires TypeScript 5 (see contract/RULES.md) | app |
| CLI | `typer` | pipeline, api |

Adding a runtime dependency to `engine` or `contract` needs a line in that folder's RULES.md saying why.

## 4. Repository layout and dependency direction

```
pyproject.toml          uv workspace root: members, ruff, pyright, import-linter config
uv.lock
contract/   ecozone_contract   Pydantic API models, openapi.json export          deps: pydantic
engine/     ecozone_engine     AreaModel, shadows, indices, rescore, greedy       deps: shapely, numpy, geopandas*, pyarrow*
pipeline/   ecozone_pipeline   offline job → area bundle (+ BigQuery copy)       deps: engine, osmnx, pvlib, …
agents/     ecozone_agents     search loop, proposers, writer, output guard     deps: engine, contract, google-genai
api/        ecozone_api        FastAPI app, store, snapshot CLI, static serving   deps: engine, contract, agents
evals/                         pytest suites that span packages, agent evals, REPORT.md
infra/                         Dockerfile, cloudbuild.yaml, deploy notes, IAM
data/                          local bundles and pipeline cache (gitignored)
```

\* used only by `engine.io` to read the bundle; scoring code works on shapely arrays and plain dataclasses.

Allowed imports (enforced by import-linter in CI):

```
contract ◄──── agents ◄──── api
   ▲              │          │
   └──────────────┼──────────┘
engine ◄──────────┴──────────┘ ◄──── pipeline
```

- `engine` imports nothing from this repo and no cloud, HTTP or LLM library.
- `contract` imports only pydantic. It does not import `engine`; `api` and `agents` convert engine results to contract models in one module each (`to_contract.py`).
- `pipeline` imports `engine` (to compute baselines with the same code), never `api` or `agents`.
- Nothing imports `api`.

## 5. Data and the area bundle

- **CRS.** Engine and bundle geometry are in UTM 43N (EPSG:32643), metres. Conversion to WGS84 happens in exactly two places: `api` when serializing GeoJSON, and `pipeline` when loading BigQuery `GEOGRAPHY`. Coordinates sent to the UI are rounded to 6 decimals.
- **Bundle.** One directory per area and version: `gs://<bucket>/areas/<area>/v<N>/` (locally `data/areas/<area>/v<N>/`). It holds GeoParquet tables (`buildings`, `blocks`, `chunks`, `wait_points`, `parcels`, `sites`) and `meta.json` (bbox, sun table, wind direction, `V_ref`, data-gap counts, sources and licences, pipeline git SHA, settings hash). Schema per table: [pipeline/RULES.md](../pipeline/RULES.md).
- **Immutable.** A published bundle version is never overwritten. The service reads `ECOZONE_BUNDLE_URI`; changing data means a new version and a config change.
- **Test fixture.** A tiny synthetic area (`engine/tests/fixtures/tiny/`, a handful of hand-placed buildings and one street) is committed, so every test runs offline in seconds. The real Deccan bundle is never needed for unit tests.
- **Settings.** Prototype settings (weights, thresholds, crown sizes, waiting-point weights, typology heights) live in one place per package: `engine/src/ecozone_engine/settings.py` for scoring, `pipeline/config/<area>.yaml` for extraction. Each constant cites the PLANNING.md section it comes from. Formulas are not restated in comments; link to PLANNING.md.
- **Licences.** OSM is ODbL: attribution in `meta.json`, served in `AreaSummary.attribution`, shown on the map and in briefs.

## 6. The API contract

- Python field names are `snake_case`; JSON is `camelCase` via `alias_generator=to_camel` and `serialize_by_alias`. TypeScript sees camelCase only.
- Models are frozen (`model_config = ConfigDict(frozen=True, extra="forbid")`).
- `contract/openapi.json` is generated (`uv run ecozone-contract export`) and committed. `app/src/api/generated.ts` is generated from it (`npm run gen:api`) and committed. `app/src/api/types.ts` re-exports and narrows the generated types; it stops hand-defining wire shapes.
- **One PR per contract change** updates the Pydantic model, `openapi.json`, `generated.ts`, the mock fixtures, and both sides' code. CI fails if any of those is out of date.
- Every file in `app/public/mock/<area>/` validates against its contract model (contract test in CI).
- Scores leave the API rounded to 1 decimal, rupees to whole rupees. Rounding happens only in `to_contract.py`, never in the engine.
- Errors use one shape: `{"error": {"code": "SITE_NOT_FOUND", "message": "…"}}` with a fitting HTTP status. Codes are an enum in `contract`.
- Contract changes needed from the current `types.ts` are tracked in [contract/RULES.md](../contract/RULES.md#changes-from-the-ui-baseline) and agreed with the U lane before the PR.

## 7. Grounding and copy rules (backend side)

These mirror PLANNING.md "Grounding rules" and UI_RULES.md §6; the backend enforces them before text reaches the UI.

- No temperature, wind-speed or energy units in any planner-facing string (`°C`, `℃`, `K`, `m/s`, `km/h`, `kWh`, `W/m²`, "degrees Celsius"). The output guard and a contract-level test on every string field of the response models both check this.
- Every number in agent text appears in that turn's tool results or planner input (guard rules: [agents/RULES.md](../agents/RULES.md#output-guard)).
- Costs are labeled planner input; never "price", "market rate" or "estimate" without that label.
- No approve, deny, permit, sanction or order language. Use "recommended", "rejected by the ventilation check", "planner decides".
- Driver tags are an enum in `contract`; agents may only name drivers the engine returned.

## 8. Performance budget

Measured with `pytest-benchmark` on the Deccan bundle and reported in `evals/REPORT.md`; CI checks the tiny fixture only.

| Step | Target |
| --- | --- |
| Service start including bundle load | < 10 s |
| `rescore`, one Repair portfolio | < 200 ms |
| `rescore`, one Protect building | < 100 ms |
| Shadows for one time with a portfolio | < 500 ms |
| Search, 3 rounds | < 60 s; returns best so far at the time limit |

## 9. Testing

| Layer | Where | Runs in CI | What |
| --- | --- | --- | --- |
| Engine unit and golden | `engine/tests/` | yes | Every formula against a hand-computed value; shadow length and direction; chunk shading |
| Engine properties | `engine/tests/` | yes | Range 0–100, determinism (10 runs byte-equal), the direction tests in PLANNING.md "Tests" (hypothesis over intervention and building settings) |
| Contract | `contract/tests/` | yes | Mock fixtures validate; openapi.json and generated.ts up to date; forbidden-unit scan over string fields |
| API | `api/tests/` | yes | Every route on the tiny fixture with the memory store and the fake LLM |
| Agents | `agents/tests/` | yes | Search loop control flow, scorer drops invalid candidates, judge stops correctly, guard accepts and rejects known texts, all with a scripted fake LLM |
| Agent evals | `evals/agents/` | no, run by hand | Live Gemini runs over fixed areas and parcels: grounding violations, tool order, Gemini vs greedy, design-search rules. Results to BigQuery `eval_results` and `evals/REPORT.md` |
| Speed | `evals/speed/` | no, run by hand | The budget in §8 on the real bundle |

- A bug fix comes with a test that failed before the fix.
- Tests never hit the network. Live-cloud tests are marked `@pytest.mark.cloud` and skipped unless `ECOZONE_CLOUD_TESTS=1`.

## 10. Tooling, CI and deploy

- One command per check, the same locally and in CI: `uv run ruff check`, `uv run ruff format --check`, `uv run pyright`, `uv run lint-imports`, `uv run pytest`. `make check` runs all of them plus the app's `typecheck`, `lint` and `build`.
- **CI** (GitHub Actions, on every PR): Python checks, app checks, contract freshness (`openapi.json`, `generated.ts`, mock validation). All must pass to merge.
- **Deploy**: merge to `main` → Cloud Build builds one image (app build copied into the Python image) → Cloud Run in `asia-south1`. Min instances 1 and session affinity during judging. GitHub authenticates to GCP through Workload Identity Federation.
- **Region**: Cloud Run, GCS, Firestore and BigQuery in `asia-south1`; Vertex Gemini through the location the model is offered in (set by env).
- **Config** comes from environment variables read by one `pydantic-settings` class per service (`ECOZONE_BUNDLE_URI`, `ECOZONE_STORE=memory|firestore`, `GOOGLE_CLOUD_PROJECT`, `ECOZONE_GEMINI_LOCATION`, `ECOZONE_MODEL_PROPOSER`, `ECOZONE_MODEL_WRITER`; the agents also read `ECOZONE_LLM=gemini|fake`). `.env.example` is committed; `.env` is gitignored.
- **Logging**: structured JSON to stdout; every line in a request or run carries `run_id` / `request_id`.

## 11. Workflow

- Branch names: `<lane>/<topic>` (`engine/shadows`, `api/rescore`, `contract/sites`). One concern per PR; small PRs merge faster.
- PR description: what changed, which rule or doc section it implements, how it was tested. Contract changes say so in the title.
- Agents (Claude and others) may open PRs; a human merges. An agent working while another agent edits the same tree uses its own git worktree.
- Commits: imperative subject, under 72 characters.
- Docs move with code: a PR that changes a formula, route, table or setting updates the doc that owns it (PLANNING.md for formulas, DESIGN.md for components, the folder RULES.md for conventions).

## 12. Definition of done (non-UI change)

- Follows this file and the folder's RULES.md.
- Numbers come from the engine; provenance fields are filled; no forbidden units or approval language.
- Contract, `openapi.json`, `generated.ts` and mock fixtures agree.
- New behaviour has tests; `make check` passes locally and in CI.
- Performance budget still holds for touched paths (benchmark run noted in the PR if a hot path changed).
- Docs updated where a decision, route, setting or formula changed.

## 13. Build order for the baseline

The order the backend gets built in, so other contributors always have something real to build against. Dates are in [TASKS.md](TASKS.md).

1. **Skeleton.** uv workspace, the five packages with empty modules, ruff, pyright, import-linter, pytest, `make check`, CI, the Dockerfile serving the current app build and `/healthz` on Cloud Run.
2. **Contract.** Pydantic models matching today's `types.ts` (minus the agreed changes), `openapi.json`, `generated.ts`, mock-fixture validation.
3. **Pipeline to bundle.** OSM extract for Deccan → blocks, 10 m chunks, parcels, sites, wait points, heights with sources, sun and wind → bundle v1. Tiny fixture area.
4. **Engine core.** `AreaModel` load, shadows, chunk shading, PSS, VCI, HEI, GCS, priority, ACS, drivers, with golden and property tests. Pipeline baselines call it.
5. **Read routes.** `GET` area, layers, hotspots, sites from the bundle. The UI can switch to `VITE_API_MODE=http`.
6. **Rescore.** Five interventions, ventilation check, the `building` change, risk label, build-out, greedy. `POST /rescore`. Snapshot command replaces the JS mock builder.
7. **Agents.** Tools, the shared search loop with fake-LLM tests, the guard and template fallback, then live Gemini. Run and explain routes over SSE.
8. **Persistence and logging.** Firestore store, BigQuery `runs` and `eval_results`, briefs.
9. **Optional data.** Earth Engine layers (heights, Sentinel-2 shares, albedo, WorldCover, Landsat heat check) as a new bundle version, if approval lands.

## 14. Open items

| Item | Owner | Status |
| --- | --- | --- |
| Exact Gemini Flash and Pro model IDs and location on Vertex | A | Verify before step 7 |
| Earth Engine approval | A | Pending |
| Default unit costs with citations | Claude | To research during step 3 (`pipeline/config/unit_costs.yaml`) |
| Contract changes agreed with the U lane | D + U | Before step 2 merges |
| GitHub → GCP Workload Identity Federation | A | Step 1 |
| `gcloud` CLI on builder machines | All | Step 1 |
