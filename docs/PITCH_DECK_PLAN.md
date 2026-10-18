# Pitch deck plan: EcoZone AI

Plan for filling **Submission Template _ AI Builder Cup.pptx** (16 slides, template order kept). The working copy is `NeuralNodes - AI Builder Cup Submission.pptx`. Content comes from [PLANNING.md](PLANNING.md) and [DESIGN.md](DESIGN.md). The deck is exported to PDF and must cover problem, solution, feasibility and scalability, with the theme stated as **Sustainability & Social Impact**.

**Story order:** Repair leads ("fix the streets people already wait on"), Protect follows ("don't undo it with the next building"). One line to repeat: *Repair and protect a city's cooling network.*

## Rules for the deck

- **No invented numbers.** Scores, benchmarks, costs and the heat-check result go in only after they are measured. Until then the slide shows a marked placeholder.
- **No temperatures or wind speeds** on any planner-facing screenshot. Surface temperature appears only on the heat-check scatter plot.
- **Lead with people and places:** a bus stop on an east–west street at 3 pm, not the technology.
- Every slide maps to a judging criterion (table at the end).

## Slide by slide

### 1. Team Details (filled in the working copy)
| Field | Content |
| --- | --- |
| Team name | NeuralNodes |
| Team leader | Ankita Sharma |
| Problem statement | Cities have no quick way to decide where trees, shade, depaving and cool roofs would cool the people who wait outdoors, or to stop new buildings breaking the breeze and green that cool a street. Theme: Sustainability & Social Impact. |

Add member names if the template allows (2–4 working professionals, 21+, JAPAC).

### 2. Template note
Delete before export.

### 3. Brief about the idea
- **Hook:** Repair and protect a city's cooling network.
- **Problem (3 bullets):** people wait in the heat on footpaths, at bus stops and in school yards with no shade; cities lack a way to spend a limited greening budget where it helps most; new legal buildings can still block breeze and pave over green.
- **Evidence (2 bullets, cited):** 10,545–20,615 heat deaths in India 2000–2020 depending on the agency (Dialogue Earth via PreventionWeb, Apr 2026); Pune's built-up area grew from 44.8% to 55.17% from 2012 to 2023 (Tiwari et al., 2025).
- **Solution:** Repair: Gemini designs a costed plan of trees, shade, depaving, pocket green and cool roofs, scored by an engine that measures footpath shade and rejects options that block the breeze. Protect: preview a proposed building's impact and find better designs.
- **Visual:** shadow map of one street at 3 pm, before and after (from real output).

### 4. Opportunities
| Question | Answer |
| --- | --- |
| How different is it? | Forma is a paid wind and microclimate tool for architects. Tree equity tools show where canopy is missing, but don't design, cost or check interventions. EcoZone AI designs a costed mix of five intervention types for a budget, checks each against ventilation and shade geometry, and explains it, using free data for Indian cities. |
| How will it solve the problem? | Gives ward and tree officials a ranked, phased, costed plan for land the city already controls (footpaths, school yards, parking, medians, roofs), at the moment budgets are set; gives planners a preview before approving large projects. |
| USP | (1) AI designs the plan, an engine scores it, and it knows when trees backfire. (2) Shade measured as geometry where people actually wait. (3) Gemini benchmarked against a greedy baseline, reported honestly. (4) Every number traceable; AI-estimated inputs labeled. |

### 5. List of features
**Repair:** priority map (heat × missing shade × waiting points × dense low-rise) · budget and unit costs · Gemini portfolio search with live progress · five intervention types · ventilation check with rejected options · shadow comparison at 1, 3 and 4 pm · phased cooling plan with field check lists.
**Protect:** proposal preview with risk label · Gemini design search (options A, B, C) · area build-out.
**Trust strip:** output guard · no temperatures or wind speeds · AI-estimated labels · never approves or orders work.

### 6. Process flow
Two rows on one map:
- **Repair:** select area → priority map → set budget → Gemini proposes portfolios → engine scores (shade, heat, green, ventilation, cost) → refine ×3 → plan and shadows → cooling plan brief.
- **Protect:** select parcel → enter proposal → engine scores → Gemini explains → design search → options A/B/C → build-out → planning brief.
Small inset: the search loop (Gemini proposer → code scorer → code judge; stop at 2 rounds or no gain).

### 7. Wireframes / mock diagrams
Real screenshot of the Repair screen if ready by Oct 17; otherwise the annotated mockup. Callouts: rejected tree row with reason, live search progress, planner-input and AI-estimated badges, arrows and text with color.

### 8. Architecture
Redraw section 1 of DESIGN.md: offline pipeline → BigQuery and Cloud Storage; one Cloud Run service with React, FastAPI, the agent layer (code router, role-based agents, one propose-score-judge search loop in plain asyncio, output guard) and the engine; Firestore; Gemini on Vertex AI. Dashed path: Landsat → heat check only.

### 9. Technologies
| Area | Technology |
| --- | --- |
| AI | Gemini on Vertex AI (model name confirmed on day 1), Google Agent Development Kit (LlmAgent, LoopAgent, callbacks) |
| Backend | Python, FastAPI, shapely, geopandas, pvlib |
| Front end | React, TypeScript, deck.gl, MapLibre GL |
| Cloud | Cloud Run, BigQuery (GEOGRAPHY), Firestore, Cloud Storage, Cloud Build, Earth Engine |
| Data | OpenStreetMap, Open-Meteo wind (ERA5), computed sun position; Landsat 8/9 for the heat check only. Open Buildings, Sentinel-2 and WorldCover are future layers, not in the shipped bundle |

Note on the slide: Google Maps tiles are not used because of the Maps Platform AI-use terms.

### 10. Estimated implementation cost
- **Free by design:** all data sources open; Earth Engine noncommercial.
- **Measured after deployment:** Gemini calls per search (at most 3), Cloud Run, BigQuery, Firestore. **TBD**
- **Intervention costs:** planner unit costs, with defaults from a cited public source. Never presented as market prices.
- **Per new city:** one pipeline run plus storage; no code changes.

### 11. Snapshots of the prototype
Five real screenshots: priority map with shadows at 3 pm; search mid-run; plan with a rejected tree row; shadows before and after; Protect options A/B/C. No pre-written scores.

### 12. Performance report / benchmarking
Report only measured results.
| Test | Report |
| --- | --- |
| Determinism, range, direction (both modes) | pass/fail |
| Shadow geometry, ventilation guard, budget | pass/fail |
| Gemini vs greedy | win/tie/loss per test area, with ACS gain and cost |
| Grounding violations | count |
| Speed: rescore, simulate, full search | measured times |
| Heat check | As measured in REPORT.md: Spearman correlation, p-value and block count on held-out blocks (the headline), all-blocks for context, scatter plot, caveats. Say plainly that held-out agreement is weak and not significant |

If a result is poor, say so and why.

### 13. Future development
- **Close the loop:** plan in winter, plant with the monsoon, measure the next summer with Landsat, recalibrate; ward staff log tree survival with geotagged photos checked by Gemini.
- **More interventions:** greening nala and river edges; street-level imagery for site checks once licensing is verified.
- **More cities:** one pipeline run per city.
- **Language:** plans in Marathi for ward offices.
- **Limits stated openly:** heuristic indices; the heat check on held-out blocks shows weak agreement with Landsat (see REPORT.md) and the other indices are not validated; shade is clear-sky geometry; albedo block-level; Open Buildings heights unmeasured in India.

### 14. Links
| Item | Status |
| --- | --- |
| GitHub public repository | Make public; no keys |
| Demo video (3 min) | Record after freeze; public link |
| Final product | Cloud Run URL, opens without login |

### 15–16. Closing
Slide 15: *Repair and protect a city's cooling network*, with three proof points (engine-scored AI plans, shade where people wait, engine-scored plans checked by tests and evals; heat index checked against Landsat as measured: weak agreement, stated plainly). Slide 16: contact and thanks. Delete if unused.

## Mapping to judging criteria

| Criterion (weight) | Slides |
| --- | --- |
| Technical merit and Gen AI (40%) | 5, 6, 8, 9, 12 |
| Problem alignment and impact (25%) | 3, 4, 13 |
| Innovation and creativity (25%) | 4, 5, 6, 7 |
| User experience (10%) | 7, 11 |

## Build order

| When | Task |
| --- | --- |
| Oct 13–14 | Slides 1, 3, 4, 9, 13 (no code dependencies) |
| Oct 15–16 | Slides 5, 6, 8 diagrams |
| Oct 17 | Slides 7, 11, 12 from real output; slide 10 cost; slide 14 links |
| Oct 18 morning | Export PDF, check no placeholders remain, submit |

## Open items

1. Member names for slide 1 if the template allows: Ankita Sharma, Abhishek Sirohi, Dhananjay (surname needed).
2. Gemini model name (slide 9).
3. Default unit-cost source (slide 10).
4. Measured results, screenshots and links (slides 11, 12, 14).
5. Precedents to verify before citing: Ahmedabad Heat Action Plan cool roofs, Telangana Cool Roof Policy (2023), Paris OASIS schoolyards, American Forests Tree Equity Score.
