# Tasks: NeuralNodes, EcoZone AI

Team of 3, about 100 to 130 person-hours from Oct 13 to Oct 18. Repair leads; Protect is second. Scope and estimates: [DESIGN.md](DESIGN.md#6-effort-estimate). Gate rules and the cut order: [PLANNING.md](PLANNING.md#build-plan-oct-13-to-18).

- **D** = Data and engine (OSM pipeline, geometry, shadows, engine, greedy, engine tests) · about 45 h
- **A** = Agents and cloud (Earth Engine, BigQuery, FastAPI, ADK, guard, deploy, agent evals) · about 43 h
- **U** = Front end (React, deck.gl, panels, brief view, accessibility; helps with deck and video) · about 33 h
- **All** = whole team · about 12 h

| Lane | Owners |
| --- | --- |
| D | Dhananjay, Ankita |
| A | Ankita, Abhishek |
| U | Abhishek (with Claude) |

Team leader: Ankita Sharma.

## Baseline build: who does what (from Oct 16, orchestrated by Claude)

Supersedes the dates in "Backend baseline (re-planned Oct 15)" below; the build order is the same as [ENGINEERING_RULES.md §13](ENGINEERING_RULES.md#13-build-order-for-the-baseline). Work runs in parallel against three agreed interfaces, so nobody waits for anybody's code:

- **Bundle schema** ([pipeline/RULES.md](../pipeline/RULES.md#bundle-tables)): between pipeline (Dhananjay) and engine (Ankita).
- **Engine public API** ([engine/RULES.md](../engine/RULES.md#public-api)): between engine (Ankita) and API and agents (Claude). Claude commits stubs with these signatures in WP1.
- **API contract** ([contract/](../contract/RULES.md)): between API (Claude) and app (Abhishek and Claude, U lane).

| WP | Work package | Owner | Reviewer | Branch | Needs | Delivers | Target |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Skeleton | Claude | Abhishek | `infra/skeleton` | — | uv workspace, five packages, engine API stubs, ruff, pyright, import-linter, pytest, `make check`, CI, Dockerfile serving the app with `/healthz` | Oct 16 |
| 2 | Contract and app types | Claude | Ankita (D), Abhishek (U sign-off) | `contract/models` | 1 | Pydantic models with the agreed changes, `openapi.json`, `generated.ts`, `types.ts` re-exports, mock validation | Oct 16 |
| 3 | Google Cloud setup | Abhishek | Ankita | `infra/gcp` | — | Project, APIs, Artifact Registry, bundle bucket, Firestore, Cloud Run service, service accounts, GitHub WIF, `gcloud` on every machine, Vertex Flash and Pro model ids verified, Earth Engine status | Oct 16 |
| 4 | Pipeline to bundle v1 (OSM only) | Dhananjay | Ankita | `pipeline/bundle-v1` | 1 (start the geometry code now) | `config/deccan.yaml`, OSM extract, blocks, 10 m chunks, height chain, parcels, sites with the canopy site rule, sun and wind, bundle writer, tiny fixture | Oct 16 night |
| 5a | Engine core | Ankita | Dhananjay | `engine/core` | 1, tiny fixture | Bundle load, shadows, chunk shading, PSS, VCI, HEI, GCS, priority, ACS, drivers; golden and property tests | Oct 16 night |
| 5b | Engine rescore and greedy | Ankita | Claude | `engine/rescore` | 5a | Five interventions, `building` change, risk label, `rescore`, single-site results, greedy with the quick-win share | Oct 17 13:00 |
| 6 | API routes and app on HTTP | Claude | Abhishek | `api/routes` | 2, engine stubs | Read routes, `rescore`, runs over SSE, explain, memory store, app HTTP adapter, `ecozone snapshot` | Oct 17 morning |
| 7 | Agents | Claude | Abhishek | `agents/search` | 2, 3 (model ids) | Shared search loop with fake-LLM tests, guard, templates, then live Gemini | Oct 17 |
| 8 | Default unit costs | Claude | Ankita | `pipeline/unit-costs` | — | `pipeline/config/unit_costs.yaml` with a cited source per row | Oct 16 |
| 9 | Deploy and persistence | Abhishek | Claude | `infra/deploy` | 1, 3 | `cloudbuild.yaml`, Cloud Run deploy from `main`, Firestore store, BigQuery `runs` | Oct 17 |
| 10 | Evals subset | Dhananjay | Ankita | `evals/baseline` | 5b, 7 | Determinism, range, direction, Gemini vs greedy, speed; `evals/REPORT.md` | Oct 17 evening |
| 11 | Submission | All (Abhishek and Claude lead video and deck) | Ankita | — | 10 | Video, deck PDF, public repo, live link | Oct 18 morning |

**Checkpoints**

- **Oct 16, end of day:** WP 1, 2, 3 and 8 merged; bundle v1 builds locally; engine indices and shadows pass on the tiny fixture.
- **Oct 17, 13:00 (Gate 2):** real `rescore` and greedy; app runs on `VITE_API_MODE=http`; both modes work end to end locally with the fake LLM.
- **Oct 17, 21:00 (Gate 3, feature freeze):** deployed on Cloud Run; live Gemini search; evals subset run.
- **Oct 18 morning:** video, deck, submit.

**How we work in parallel**

- One branch per work package, small PRs, squash merge. Claude opens PRs; the named reviewer approves and merges (Ankita merges anything urgent as team leader).
- A blocked owner codes against the interface (stub, fixture or contract) instead of waiting, and says so in the PR.
- A change to one of the three interfaces is its own PR, agreed by both sides first.
- Earth Engine stays off the critical path: OSM-only bundle v1 first, Earth Engine layers as bundle v2 only if approval lands before Gate 2.

## Oct 13 (today): contracts and foundations

- [x] **All:** assign lane owners and name the team leader (deck slide 1)
- [ ] **All:** confirm registration (2–4 members; email support if unsure) and eligibility (working professionals, 21+, JAPAC)
- [ ] **All:** agree the API contracts: Pydantic schemas for `Change`, `AreaResult`, Protect simulate, and the SSE event types, so all lanes build against stubs from today
- [ ] **D:** fill `pipeline/config/pune.yaml` (both candidate boxes, EPSG:32643, reference date 15 April, road-class widths)
- [ ] **D:** OSM extract for both boxes; count buildings with heights, sidewalks and waiting points in each; freeze the better box
- [ ] **D:** blocks from the road network; footpath segments (~50 m, sidewalks or derived road edges, clipped 10 m back from junctions)
- [ ] **A:** chase the Earth Engine approval; meanwhile write the `ee_layers.py` scripts against the public datasets
- [ ] **A:** confirm the current Gemini model name on Vertex AI; create the service account and roles (BigQuery, Firestore, Storage, Vertex AI)
- [ ] **A:** deploy an empty FastAPI service on Cloud Run that serves a placeholder React build (proves the one-container path)
- [ ] **U:** Vite + React + TypeScript scaffold; MapLibre with a no-key vector basemap (check its terms); deck.gl overlay with stub layers
- [ ] **U:** mode switch (Repair default), app layout, Zustand store, API client against stubs

## Oct 14: Gate 1, engine on real data

Passes when blocks, footpaths and baseline indices including PSS exist for the frozen area, and the range and determinism tests pass. If it fails: OSM proxy indices and default roof albedo at once.

- [ ] **D:** sun positions for 13:00, 15:00, 16:00 IST (pvlib); wind direction from Open-Meteo, checked against the data
- [ ] **D:** heights per building (OSM levels × 3 m, else Open Buildings, else storey default, with source column)
- [ ] **D:** shadow engine and PSS per segment; shadow geometry test (known height → expected length and direction)
- [ ] **D:** per-block attributes; VCI, HEI (with roof albedo term), GCS; driver tags
- [ ] **D:** classification: Protect parcels, Repair candidate sites per site rule, built-form class, waiting-point weights
- [ ] **D:** priority and ACS; determinism and range tests
- [ ] **A:** Earth Engine layers (if approved): heights, Sentinel-2 shares, roof albedo (choose and cite the coefficient set), WorldCover, Landsat LST, image clips
- [ ] **A:** BigQuery schema and loader; GCS layout; baseline shadows exported as GeoJSON
- [ ] **A:** FastAPI area loading at startup and `GET /areas`, `/layers`, `/hotspots`
- [ ] **U:** deck.gl layers on real data: priority blocks, extruded buildings, footpaths by PSS, waiting points, shadows with a time slider
- [ ] **Gate check:** pass, or switch to fallbacks

## Backend baseline (re-planned Oct 15)

No backend code existed on Oct 15, so the D and A lanes follow the build order in [ENGINEERING_RULES.md](ENGINEERING_RULES.md#13-build-order-for-the-baseline). The dated lists below still describe the outcome each gate needs; this list is the order to get there. Each step is one or more PRs to `main`.

- [ ] **Oct 15:** 1 skeleton (uv workspace, CI, Dockerfile, `/healthz` on Cloud Run) · 2 contract (Pydantic models, `openapi.json`, generated TS, mock validation; changes agreed with U)
- [ ] **Oct 16 morning:** 3 pipeline → Deccan bundle v1 (OSM, 10 m chunks, typology heights, sun, wind, sites, parcels) · 4 engine core with golden and property tests · 5 read routes; UI tries `VITE_API_MODE=http`
- [ ] **Oct 16 afternoon (Gate 2):** 6 interventions, `building` change, `rescore`, greedy; snapshot replaces the JS mock builder
- [ ] **Oct 17 (Gate 3):** 7 agents, search loop, guard, runs over SSE · 8 Firestore store, BigQuery `runs` and `eval_results`, briefs · deploy
- [ ] **If EE approval lands:** 9 Earth Engine layers as bundle v2; heat check

## Oct 15: Repair end to end

- [ ] **D:** interventions (`tree_row`, `shade`, `depave`, `pocket_green`, `cool_roof`) and incremental `rescore`; ventilation check with canopy obstruction
- [ ] **D:** greedy baseline; Repair direction tests; ventilation guard test; budget test
- [ ] **A:** `POST /rescore`, `/greedy`, `/sites`, `/shadows?portfolio=`
- [ ] **A:** ADK agents and tool wrappers; generic `LoopAgent` search (Gemini proposer, code scorer, code judge); SSE progress events
- [ ] **A:** output guard as `after_model_callback`; template fallback
- [ ] **U:** budget and unit-cost panel (planner-input badges); live search progress; plan table with rejected rows; shadow before/after
- [ ] **All:** set default unit costs from a cited public source (for example municipal tender rates), labeled planner input

## Oct 16: Gate 2, both modes end to end

Passes when Repair (priority, search, plan) and Protect (preview, design search, build-out) work locally. If it fails: search rounds to one; build-out to one prepared street.

- [ ] **D:** Protect: `apply_building`, simulate, risk label (including PSS drop), build-out through the shared `rescore`; Protect direction tests
- [ ] **A:** Protect routes; design search on the same loop; Planning Advisor: cooling plan and planning brief
- [ ] **A:** imagery reading with confidence, disagreement flags and field check lists for Repair sites
- [ ] **A:** Firestore persistence of sessions, portfolios, scenarios, plans; `runs` logging to BigQuery
- [ ] **U:** Protect panels: sliders, before/after with arrows and numbers, explain, option cards with Apply, build-out view
- [ ] **U:** brief view (printable HTML); AI-estimated, disagreement and planner-input badges
- [ ] **All:** run both flows end to end on the frozen area
- [ ] **Gate check**

## Oct 17: Gate 3, feature freeze

Passes when deployed on Cloud Run, evals run, and the demo area and parcel are chosen. After this, fix only what breaks the demo.

- [ ] **A:** full deploy (one container, min instances 1, session affinity); opens without a login
- [ ] **D / A:** run all evals; results to `eval_results` and `evals/REPORT.md` (including Gemini vs greedy and the heat check)
- [ ] **D:** tune thresholds and weights on the tuning half only; report on the held-out half
- [ ] **All:** choose the demo area and parcel from real output; no pre-written scores
- [ ] **U:** accessibility pass (keyboard, legends in words, arrows and text with color)
- [ ] **All:** deck slides 5–13 from real screenshots and results ([PITCH_DECK_PLAN.md](PITCH_DECK_PLAN.md))
- [ ] **A:** check no keys in code or history; billing budget alert set
- [ ] **Gate check**

## Oct 18: submit in the morning

- [ ] **All:** record the 3-minute video from real output (script in PLANNING.md); keep a backup recording
- [ ] **All:** upload as a public YouTube, Vimeo or Drive link; check it plays logged out
- [ ] **All:** finish the deck, remove placeholders, export to PDF (problem, solution, feasibility, scalability; theme stated)
- [ ] **All:** README: measured evaluation results and run instructions
- [ ] **All:** make the repository public; check the live link opens without a login; all materials in English
- [ ] **All:** submit repo, video, deck PDF and live link, leaving time for a failed upload

## Cut order (only when a gate fails)

1. Satellite layers become OSM proxy indices; roof albedo uses a labeled default; the heat check moves to future work.
2. Imagery reading shrinks to field check lists only.
3. Build-out runs on one prepared street.
4. Search rounds drop from three to one.
5. 3D building extrusion and visual polish.

Never cut: Repair with all five interventions, the shade score, the Protect preview.

## Open questions

- [ ] Earth Engine approval (applied, waiting)
- [ ] Gemini model name on Vertex AI
- [x] Team leader and member names (Ankita Sharma leads)
- [ ] Registration status
- [ ] Source for default unit costs
- [x] Basemap provider: OpenFreeMap Positron (app/UI_RULES.md)
- [x] Demo area: Deccan box, frozen Oct 15
- [ ] Sentinel-2 albedo coefficient set and citation
