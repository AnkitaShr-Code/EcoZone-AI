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
- [ ] Team leader and member names
- [ ] Registration status
- [ ] Source for default unit costs
- [x] Basemap provider: OpenFreeMap Positron (app/UI_RULES.md)
- [x] Demo area: Deccan box, frozen Oct 15
- [ ] Sentinel-2 albedo coefficient set and citation
