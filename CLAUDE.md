# CLAUDE.md: EcoZone AI

Team NeuralNodes · Google Cloud AI Builder Cup 2026 · theme Sustainability & Social Impact · submission due **Oct 18, 2026**.

EcoZone AI helps a city cool the streets people already wait on (**Repair**, the lead mode) and stops new buildings from undoing it (**Protect**). Gemini proposes and explains; a deterministic Python engine scores. Product, formulas and decisions live in `docs/`; this file is what you need before touching code.

## Read first (only what the task needs)

| Working on | Read |
| --- | --- |
| Anything outside `app/` | `docs/ENGINEERING_RULES.md`, then the `RULES.md` in the folder you touch |
| `app/` | `app/UI_RULES.md` |
| Formulas, site rules, agent and tool contracts, trust rules | `docs/PLANNING.md` (formulas exist **only** there) |
| Components, routes, data stores, flows | `docs/DESIGN.md`, `docs/ARCHITECTURE.md` |
| Who builds what, gates, cut order | `docs/TASKS.md` |
| Deck, video, README claims | `docs/PITCH_DECK_PLAN.md` |

If `AGENTS.md` exists, read it too. On any conflict, `docs/ENGINEERING_RULES.md` and the folder's `RULES.md` win, then this file, then `AGENTS.md`. Flag the conflict in your PR description so the files can be reconciled.

## The two rules every change must keep

1. **Sliders never wait for AI.** Any route the UI calls on a control change runs the engine only (target < 200 ms per portfolio, < 100 ms per Protect building). Gemini runs only behind the search and explain routes.
2. **The engine is the only place a number is made.** Pipeline baselines, API responses, agent tool results, mock fixtures and eval values all come from `engine/` functions. Never re-implement a formula elsewhere, even "just for the baseline". All scoring goes through one `rescore(area, changes, unit_costs)`.

## Repository map and dependency direction

```
contract/  Pydantic API models, openapi.json          deps: pydantic only
engine/    AreaModel, shadows, indices, rescore       no repo imports, no cloud/HTTP/LLM libs
pipeline/  offline job -> area bundle                 may import engine
agents/    ADK agents, search loop, output guard      imports engine, contract
api/       FastAPI, store, snapshot CLI               imports engine, contract, agents
app/       React + TypeScript + deck.gl + MapLibre    talks to api over REST and SSE
evals/     cross-package tests, REPORT.md             infra/  Dockerfile, deploy
```

`import-linter` enforces this in CI. Nothing imports `api`. `contract` never imports `engine`; `api` and `agents` convert engine results in their own `to_contract.py`.

## Commands

```bash
uv sync
make check                                   # ruff, pyright, import-linter, pytest + app typecheck/lint/build
uv run ruff check && uv run ruff format --check
uv run pyright && uv run lint-imports && uv run pytest -q
uv run pipeline <step|all> --area deccan     # steps: osm sun_wind heights geometry classify attributes bundle baselines
uv run ecozone-contract export               # regenerate contract/openapi.json
cd app && npm install && npm run dev         # app alone on mock data (:5173)
cd app && npm run gen:api                    # regenerate app/src/api/generated.ts
make api                                     # API on :8000 over data/bundles/<area>/
make app-http                                # app on the API (VITE_API_MODE=http)
uv run ecozone snapshot --area deccan        # refresh app/public/mock/<area>/ from real engine output
```

Live-cloud tests are marked `@pytest.mark.cloud` and skipped unless `ECOZONE_CLOUD_TESTS=1`. Tests never hit the network otherwise.

## Hard rules (a violation is a review blocker)

**Engine** (`engine/RULES.md`)
- Pure: no I/O outside `io.py`, no network, no randomness, no wall clock, no global mutable state; never mutate the `AreaModel`.
- Deterministic: iterate in sorted id order, stable sorts with id tie-breakers, no `set` iteration in output paths, no float rounding inside the engine.
- Every weight, threshold, radius and crown size comes from `settings.py` and cites its PLANNING.md section. No numeric literals in scoring code (0, 1, 100 and unit conversions excepted).
- Metres in EPSG:32643; angles in degrees, bearings and sun azimuth clockwise from north.
- pyright strict. Results are frozen dataclasses, not dicts.

**Data and bundle** (`pipeline/RULES.md`)
- Network and raster work only in `pipeline/`. The live service reads one immutable bundle (`ECOZONE_BUNDLE_URI`) and never calls OSM, Earth Engine or Open-Meteo.
- A published bundle version is never overwritten. Changing, renaming or dropping a bundle column is a schema change and its own PR.
- No area-name branching in code: onboarding an area changes YAML only.
- Every fallback (typology height, derived footpath, road-class width, default albedo, OSM-proxy shares) is a `*_source` column on the row **and** a count in `meta.json` `data_gaps`. Nothing fills a gap silently.
- Pipeline output is reproducible on one platform; floats differ in the last digits across platforms (PROJ, GEOS, BLAS). Compare bundles across platforms with tolerances, never regenerate the committed fixture to silence a mismatch.

**Contract and API** (`contract/RULES.md`)
- Contract first: a field exists only if it is in `contract/`. One PR per contract change updates the model, `openapi.json`, `generated.ts`, the mock fixtures and both sides' code.
- JSON is camelCase, Python is snake_case. Models are frozen with `extra="forbid"`.
- Round only in `to_contract.py` (scores to 1 decimal, rupees to whole rupees). Errors use the single `{"error": {"code", "message"}}` shape.

**Grounding and copy** (every planner-facing string, enforced by the output guard and a contract test)
- No temperature, wind-speed or energy units (`°C`, `K`, `m/s`, `km/h`, `kWh`, `W/m²`). The tool never reports temperatures or wind speeds.
- Every number in agent text appears in that turn's tool results or planner input. Agents may only name driver tags the engine returned.
- Costs are labeled planner input, never "price" or "market rate".
- Never approve, deny, permit, sanction or order. Use "recommended", "rejected by the ventilation check", "planner decides".
- AI-estimated values and defaults are always labeled. Indices are screening indicators, not physical measurements.

**Security**: no API keys or key files anywhere, in code, env files or history. ADC locally, service account on Cloud Run, Workload Identity Federation in CI. `.env.example` is committed; `.env` is gitignored.

**Stack**: Python 3.12 (not 3.13+), `uv` workspace, shapely >= 2. Adding a runtime dependency to `engine` or `contract` needs a line in that folder's `RULES.md` saying why. Upgrade pinned dependencies only in a PR that does nothing else.

## Testing expectations

- A formula change needs a golden test with the hand-computed expected value in the docstring, plus the relevant direction test from PLANNING.md "Tests" as a `hypothesis` property.
- Determinism (10 runs byte-equal after JSON serialization) and range (0 to 100) stay green on `engine/tests/fixtures/tiny/`.
- A bug fix comes with a test that failed before the fix.
- Agent tests run with a scripted fake LLM. Live Gemini runs are evals, run by hand, results to `evals/REPORT.md`.
- Report only measured results. No score, benchmark, cost or heat-check number goes into the README, deck or video script until it has been run. Until then, use a marked placeholder.

## How to work in this repo

- **Evidence before "done".** Show the real diff and the actual command output (`make check`, the failing test before and after). Do not summarize test results in prose. Say plainly what you did not run.
- **Debug from evidence.** Reproduce, read the actual error, then fix. No speculative fixes; if a cause is a hypothesis, say so and give the command that would confirm it.
- **Stay inside your package.** Work against the agreed interfaces (bundle schema, engine public API in `engine/RULES.md`, contract) using stubs or the tiny fixture. A change to one of those interfaces is its own PR, agreed with the other side first. Do not change a signature or a schema as a side effect.
- **Docs move with code.** A PR that changes a formula, route, table or setting updates the owning doc (PLANNING.md for formulas, DESIGN.md for components, the folder `RULES.md` for conventions). To break a rule, change the rule in the same PR with the reason.
- **Branches and PRs.** `<lane>/<topic>` (`engine/shadows`, `contract/sites`), one concern per PR, squash merge, CI must pass. Commit subjects are imperative and under 72 characters. You may open PRs; a human merges. Use your own git worktree if another agent is editing the same tree.
- **Definition of done.** Follows this file and the folder's `RULES.md`; numbers come from the engine with provenance filled; contract, `openapi.json`, `generated.ts` and mocks agree; new behaviour is tested; `make check` passes; touched hot paths still meet the performance budget; docs updated.
- Prefer the smallest change that does the job. Do not refactor, reformat or upgrade unrelated code.

## Decisions you must not make alone

Surface these to the team with the data and the options instead of choosing:
- Changing a PLANNING.md prototype setting, such as the dense low-rise thresholds (PLANNING default coverage 0.5, median footprint 60 m², 2 floors; the Deccan config loosens them and needs a team decision).
- Cutting scope. The cut order in `docs/TASKS.md` applies only when a gate fails. Never cut Repair with all five interventions, the shade score, or the Protect preview.
- Gemini model ids (set by env, verified against the Vertex model list before first use), Earth Engine usage, the source for default unit costs.
- Any bundle, engine-API or contract change.

## Hackathon constraints that shape code

- Deliverables: Cloud Run prototype that opens **without a login**, public GitHub repo with no keys, demo video of 3 minutes, PDF deck in the prescribed template, theme stated as Sustainability & Social Impact. All materials in English.
- The submission description must say how Firebase/Firestore, Cloud Run and Gemini are used. Keep those visible in the architecture, and keep Firestore persistence and Gemini on Vertex AI working in the deployed build.
- One Cloud Run service serves the UI and the API (region `asia-south1`). Min instances 1 and session affinity during judging.
- No Google Maps tiles or Street View (Maps Platform AI-use terms). Basemap is OpenFreeMap. OSM attribution (ODbL) must be shown on the map and in briefs.
- Gemini access is Vertex AI via service account only. Flash tier for the search proposer, Pro tier for explanations and briefs. At most 3 Gemini calls per search.
- The demo runs on the frozen Deccan Gymkhana to Fergusson College box (`deccan`). Do not claim results for any other city.

## Front end (see `app/UI_RULES.md` for the full rules)

- The app runs on mock data by default (`app/public/mock/<area>/`, a snapshot of real engine output) or on the API with `VITE_API_MODE=http`.
- Types come from `app/src/api/generated.ts`; do not hand-define wire shapes.
- Change direction is shown with arrows and text as well as color. Controls are keyboard operable. Legends are in words. Every Gemini statement traces to a number on screen.

## Working agreement

1. **No attribution lines.** Commit messages and PR descriptions contain no "Co-Authored-By" and no "Generated with" lines.
2. **Branch per task.** Work on a branch named `<lane>/<topic>`; never commit directly to main; never `git push --force` to a shared branch.
3. **Destructive commands require confirmation.** Before any `reset --hard`, `branch -D`, `worktree remove`, or `stash drop`: print exactly what would be removed and wait for explicit approval before running.
4. **Raw output in reports.** Report results with raw command output, not prose summaries. Mark anything unverified as "claimed, unverified".
5. **Never remove the primary clone.** Never run `git worktree remove` on the directory that holds `.git/` (the primary clone).