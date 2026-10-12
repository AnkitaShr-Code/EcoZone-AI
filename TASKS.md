# Tasks: NeuralNodes, EcoZone AI

Team of 3. Lanes follow the suggested split in the [planning document](EcoZoning%20AI%20Climate%20Impact%20Preview%20for%20Building%20Proposals.md):

- **D** = Data and engine
- **A** = Agents (Gemini, ADK, output guard)
- **U** = App (frontend, Cloud Run)
- **All** = whole team

Assign names next to each lane before starting. Tick items as they finish. Gate rules and fallbacks are in the planning doc's six-day plan.

| Lane | Owner |
| --- | --- |
| D | _TBD_ |
| A | _TBD_ |
| U | _TBD_ |

## Oct 12 (today)

- [ ] **All:** assign lane owners (table above) and name the team leader
- [ ] **All:** confirm the team is registered as 2–4 people (site showed registration closed Oct 11; timeline lists team formation to Oct 14; email support if unsure)
- [ ] **All:** confirm every member is a working professional, 21 or older, based in JAPAC
- [ ] **D:** register the Google Cloud project for Earth Engine as noncommercial; read the eligibility terms (if refused: Copernicus Data Space for Sentinel-2, skip Landsat validation)
- [ ] **A:** check the current Gemini model name against the Google Cloud model list
- [ ] **A:** ADK skeleton with stub tools returning fixed fake values
- [ ] **U:** create the Cloud Run project and repo structure (`pipeline/`, `engine/`, `agents/`, `app/`, `evals/`)

## Oct 13

- [ ] **D:** compare Shivajinagar and Kothrud by the share of buildings with a height (OSM floors tag or Open Buildings); freeze the better box
- [ ] **D:** pull OSM buildings, roads, parks and water for the ~2.5 km × 2.5 km box
- [ ] **D:** spot-check about 10 Open Buildings heights against OSM floors tags or the image clips
- [ ] **D:** verify the prevailing wind direction and season against the downloaded Open-Meteo data
- [ ] **A:** write the six tool contracts as typed schemas; stub `simulate_scenario`
- [ ] **U:** deploy an empty app to Cloud Run (proves the deploy path); it must open without a login
- [ ] **U:** map with candidate parcels
- [ ] **All:** deck slides 1, 3, 4, 5, 9, 13 from the doc (see [PITCH_DECK_PLAN.md](PITCH_DECK_PLAN.md))

## Oct 14: Gate 1, engine on real parcels

Passes when indices are computed for real parcels in the frozen area, the range and determinism tests pass, and the heat check has a first number. If it fails: switch to OSM proxy indices at once.

- [ ] **D:** define parcels (road-network blocks with low coverage or tagged vacant/open)
- [ ] **D:** Earth Engine layers: Sentinel-2 median, WorldCover shares, Landsat surface temperature
- [ ] **D:** per-parcel attributes (neighbors' height, street width, canyon axis, built run, distances, buffer shares, reference volume)
- [ ] **D:** engine computes VCI, HEI, GCS, risk label and driver tags
- [ ] **D:** determinism test (ten runs match exactly) and range test (0–100)
- [ ] **D:** first heat-check number (Spearman on held-out half, block count)
- [ ] **D:** load parcel table to BigQuery
- [ ] **A:** wire `get_parcel_context` and `simulate_scenario` to the engine
- [ ] **A:** output guard (reject numbers not in the turn's tool results, reject forbidden units; regenerate once, then fall back to a template)
- [ ] **U:** sliders and the before/after panel against stub data
- [ ] **Gate check:** pass or switch to OSM proxies

## Oct 15

- [ ] **D:** pick the test parcels: wide riverfront, dense interior block, isolated corner plot
- [ ] **D:** direction sweep test (more height or footprint never improves VCI or lowers HEI; more green never raises HEI or lowers GCS)
- [ ] **D:** `simulate_buildout`, capped at about 30 parcels; measure its speed
- [ ] **D:** export the true-color and vegetation false-color image clips per candidate parcel
- [ ] **A:** design search loop (propose four, score, refine; stop at three rounds or when no candidate beats the best by more than 2 points)
- [ ] **A:** options A, B and C selection from scored candidates only
- [ ] **U:** option cards and live design-search progress

## Oct 16: Gate 2, full flow works locally

Passes when select, simulate, explain, design search and area build-out work end to end locally. If it fails: cut the design search to one round and keep the loop code behind a setting.

- [ ] **A:** `analyze_imagery` with confidence levels, the 15-point disagreement flag and AI-estimated labels
- [ ] **A:** explanation with fixed parts (diagnosed impact, drivers, options and trade-offs, recommendation, caveats)
- [ ] **A:** `format_planning_brief`
- [ ] **A:** Gemini summary of what loses most in the build-out view
- [ ] **U:** area build-out view (street selection, envelope input, parcels colored by risk label plus text and arrows, area averages)
- [ ] **U:** data badges for AI-estimated and disagreement flags
- [ ] **U:** accessibility basics: keyboard-operable sliders, visible labels, one-sentence index definitions on hover or focus
- [ ] **All:** run the whole flow once end to end on a test parcel
- [ ] **Optional if the gate passes early:** Gemini searches area rules (height cap, minimum green share)
- [ ] **Gate check**

## Oct 17: Gate 3, feature freeze

Passes when deployed on Cloud Run, evals run, and the demo parcel is chosen. After this, fix only what breaks the demo.

- [ ] **U:** deploy the full app to Cloud Run; check it opens without a login
- [ ] **D / A:** run the evals in `evals/`: determinism, range, direction, grounding, tool use (ten parcels), design search, speed, heat check
- [ ] **D:** tune the risk-label thresholds and weights on the first half of blocks only; report on the held-out half
- [ ] **All:** choose the demo parcel from real output; do not pre-write scores into the script
- [ ] **All:** capture the prototype screenshots (deck slide 11)
- [ ] **All:** fill deck slide 12 with measured results, whatever they are; slide 10 cost after deployment
- [ ] **All:** draft deck slides 6, 7 and 8 (flow, wireframe, architecture)
- [ ] **A:** confirm no keys in the code; secrets come from environment variables
- [ ] **Gate check**

## Oct 18: Submit (do it in the morning)

- [ ] **All:** record the 3-minute demo video from real output; keep a backup recording
- [ ] **All:** upload the video as a public YouTube, Vimeo or Drive link; check it plays when logged out
- [ ] **All:** finish the deck, remove every placeholder, and export to PDF (covers problem, solution, feasibility, scalability; theme stated as Sustainability & Social Impact)
- [ ] **All:** update the README with measured evaluation results and run instructions; add a licence
- [ ] **All:** make the GitHub repository public; check there are no keys in the code or history
- [ ] **All:** check the Cloud Run link opens without a login
- [ ] **All:** check all materials are in English
- [ ] **All:** submit repo, video, deck PDF and live link with time left for a failed upload

## If time runs short (cut in this order)

1. Satellite indices become OSM proxy indices; the heat check is skipped and listed as future work.
2. Design search drops from three rounds to one.
3. Area build-out runs on one prepared street instead of any selected area.
4. UI polish is reduced; the logic and the demo path stay.

## Open questions to settle early

- [ ] Earth Engine noncommercial eligibility for a hackathon entry
- [ ] Prevailing wind direction and season (verify against downloaded data before fixing in the engine)
- [ ] Open Buildings heights in the frozen area (spot-check about 10 buildings)
- [ ] Gemini model name
- [ ] Team registration status
