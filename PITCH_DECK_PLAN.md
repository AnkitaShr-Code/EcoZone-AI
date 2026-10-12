# Pitch deck plan: EcoZone AI

Plan for filling **Submission Template _ AI Builder Cup.pptx** (16 slides, template order kept). Content comes from the [planning document](EcoZoning%20AI%20Climate%20Impact%20Preview%20for%20Building%20Proposals.md). The deck is exported to PDF and must cover problem, solution, feasibility and scalability, with the theme stated as **Sustainability & Social Impact**.

Template note (slide 2): download the template as .pptx and edit the copy; do not send edit requests.

## Rules for the deck

- **No invented numbers.** Prototype scores, benchmarks and the heat-check result go in only after they are measured. Until then the slide shows the marked placeholder below.
- **No temperatures or wind speeds** on any planner-facing screenshot. Surface temperature appears only on the heat-check scatter plot (slide 12).
- **Lead with the decision gap**, not the technology: cities ask "Can we build here?" and not "What happens to the neighborhood?"
- Every slide should map to a judging criterion (see the last table).

## Slide by slide

### 1. Team Details
| Field | Content |
| --- | --- |
| Team name | **NeuralNodes** |
| Team leader | **TBD, needs the team** (the doc names Abhishek Sirohi as author; confirm who leads) |
| Problem statement | Building proposals are checked against fixed rules and never against what they do to the airflow and heat of the blocks around them. |
| Theme (add a line) | Sustainability & Social Impact |

Also add team members' names, since the checklist requires 2–4 working professionals aged 21+ in JAPAC.

### 2. Template note
Keep as is, or delete before export. Remove the "refrain from sending edit requests" note from the final PDF if the template allows.

### 3. Brief about the idea
Carries the problem and the pitch in one slide.
- **Hook:** A climate impact preview before a permit.
- **Problem (3 bullets):** legal buildings can still block breeze and hold heat; outdoor workers, the elderly and children pay; once a cooling corridor is built over it cannot be restored.
- **Evidence (2 bullets, cited on slide):** India recorded 10,545–20,615 heat deaths 2000–2020 depending on the agency (Dialogue Earth via PreventionWeb, Apr 2026); Pune's built-up area grew from 44.8% to 55.17% from 2012 to 2023 (Tiwari et al., 2025).
- **Solution in one sentence:** a decision-support copilot that previews a proposal's effect on ventilation, heat and green connectivity, searches for better designs with Gemini, and shows the cumulative effect of a whole street building out.
- **Visual:** one before/after pair of bars (placeholder until real parcel output exists).

### 4. Opportunities
Three template questions, one block each.
| Question | Answer |
| --- | --- |
| How different is it from existing ideas? | Tools like Autodesk Forma are paid and aimed at architects in early design. EcoZone AI is aimed at the official reviewing a proposal: free public data, one-minute screening, plain-language explanation, AI design search. Complements a detailed study; does not replace one. |
| How will it solve the problem? | Gives planners the missing question's answer at three existing moments: large projects, development plan revisions, and making the case for a rule (height cap, minimum green share). Not a new mandatory permit step. |
| USP | (1) Gemini proposes, an engine scores, Gemini refines: every number is engine-computed. (2) Area build-out shows the cumulative effect. (3) Heat index checked against satellite measurement. (4) AI-estimated inputs are labeled. |

### 5. List of features
Six features, one line each, grouped:
1. Parcel selection and baseline indices (VCI, HEI, GCS, 0–100).
2. Proposal input: floors, footprint %, green %, orientation.
3. Before/after preview with a LOW / MODERATE / HIGH risk label and named drivers.
4. Gemini design search: three ranked options (A developer maximized, B balanced, C climate optimized), shown live as candidates are scored.
5. Area build-out: one envelope on every vacant parcel on a street, all parcels rescored.
6. Aerial-imagery reading with disagreement flags and AI-estimated labels; planning brief output.

Trust strip along the bottom: output guard, no physical units, never approves or denies.

### 6. Process flow / use-case diagram
Linear flow, one row of 7 steps, with the planner as the actor:
select parcel → enter building → engine scores baseline and proposed → Gemini explains drivers → design search (propose, score, refine, up to 3 rounds) → options A/B/C → planning brief. A branch from step 2 to **Area build-out** → area averages, HIGH parcel count.

Second small diagram: the design search loop (Gemini proposes 4 candidates → `simulate_scenario` scores → drop candidates breaking the floor-area rule → refine → stop at 3 rounds or <2 points gain).

Source: "What it does" and "Design search loop" sections.

### 7. Wireframes / mock diagrams (optional)
Include. Use a real screenshot if the app is ready by Oct 17, otherwise a labeled wireframe of the one screen: map (left); parcel analysis, inputs, before/after, explain, option cards, build-out (right); data badges. Annotate three callouts: arrows plus text for change direction (accessibility), live design-search progress, AI-estimated badge.

### 8. Architecture diagram
Redraw the doc's four layers and one guard:
Planner app → Agent layer (Orchestrator; Spatial Analyst, Scenario Analyst, Planning Advisor) → Scoring engine (only place a score is computed) → Preprocessed data (BigQuery, Firestore, image clips) → Output guard → planner. Show the dashed evaluation-only path (Landsat surface temperature to heat check) separately. Add the offline pipeline (OSM, Open Buildings, Sentinel-2, WorldCover, Open-Meteo → BigQuery) on the left.

### 9. Technologies to be used
| Area | Technology |
| --- | --- |
| AI | Gemini (**confirm the current model name against the Google Cloud model list before coding**); Google Agent Development Kit |
| Compute and hosting | Cloud Run |
| Data stores | BigQuery (GEOGRAPHY), Firestore |
| Geospatial processing | Google Earth Engine (noncommercial), Overpass API |
| Data | OpenStreetMap, Google Open Buildings 2.5D Temporal, Sentinel-2, ESA WorldCover, Open-Meteo (ERA5), Landsat 8/9 |
| App | Frontend with map; scoring engine in plain code |

Add a one-line note: Google Maps satellite tiles are deliberately not used because of the Maps Platform AI-use terms.

### 10. Estimated implementation cost (optional)
Include only what is known; do not invent a figure.
- **Free by design:** all data sources are open or free for non-commercial use; Earth Engine Community tier gives 150 compute-hours a month at no charge.
- **Usage-based, to be measured:** Gemini calls per design search, Cloud Run, BigQuery, Firestore.
- **Action:** after the Oct 17 freeze, compute cost per design search and per month for a pilot of N planner sessions, using the Google Cloud pricing calculator. **TBD**
- **Per new city:** one preprocessing job run plus storage; no code changes.

### 11. Snapshots of the prototype
Four real screenshots, taken from the demo parcel chosen on day 5:
1. Selected parcel with baseline indices and a data flag.
2. Before/after with risk label and Explain.
3. Design search mid-run, then options A/B/C.
4. Area build-out with parcels colored by risk label.

Do not write scores into the script or slide in advance; capture from real output.

### 12. Prototype performance report / benchmarking
Report only measured results, whatever they are. Layout: one table (test, result) plus the heat-check scatter plot.
| Test | Result to report |
| --- | --- |
| Determinism (10 runs) | pass/fail |
| Range (0–100) on riverfront, dense interior, isolated corner parcels | pass/fail |
| Direction sweep | pass/fail |
| Grounding violations | count |
| Tool-use success over ten parcels | rate |
| Design search (B keeps floor-area share, C beats A) | pass/fail per parcel |
| Speed: engine per scenario, preview, design search | measured times |
| Heat check: Spearman correlation and block count on held-out blocks | value, with the two caveats (surface not air temperature; shared inputs) |

If a result is poor, state it and the cause. If the satellite steps fell back to OSM proxies, mark the heat check "skipped, future work".

### 13. Additional details / future development
- **Scalability:** a new city means changing the bounding box, wind direction and road-class width defaults, then rerunning the same job. Claimed for the demo area only until a second city is run.
- **Next steps:** validate and calibrate with a partner who can supply measurements or detailed studies for the same area; run a second city; search area rules (height cap, minimum green share) with the same Gemini loop if the Oct 16 gate passes early.
- **Limits stated openly (one line each):** heuristic indices, only heat is validated; Open Buildings height accuracy unmeasured in India; parcels are road-network blocks, not legal plots; wind is a seasonal direction.
- **What we will not claim:** temperatures, wind speeds, fluid dynamics, forecasts, permit decisions.

### 14. Links
| Item | Source | Status |
| --- | --- | --- |
| GitHub public repository | This repo, made public | Needs no keys in code; created during the hackathon |
| Demo video (3 min) | Public YouTube, Vimeo or Drive link | Record after freeze; keep a backup |
| Final product | Cloud Run URL, opens without login | Deploy an empty version on Oct 13 to prove the path |

### 15–16. Closing slides
The template's last two slides are blank. Suggested use: slide 15 as a one-line takeaway ("Ask what happens to the neighborhood, before the permit") with the three headline claims; slide 16 as contact and thanks. Delete either if unused.

## Mapping to judging criteria

| Criterion (weight) | Slides that carry it |
| --- | --- |
| Technical merit and Gen AI (40%) | 5, 6, 8, 9, 12 |
| Problem alignment and impact (25%) | 3, 4, 13 |
| Innovation and creativity (25%) | 4, 5, 6 |
| User experience and design (10%) | 7, 11 |

## Build order and owners

| When | Task |
| --- | --- |
| Oct 13 | Fill slides 1, 3, 4, 5, 9, 13 from the doc (no dependencies on code). Confirm the team leader, member names and Gemini model name. |
| Oct 14–16 | Draw slides 6 and 8. Slide 7 wireframe if no UI yet. |
| Oct 17 (freeze) | Capture slide 11 screenshots; fill slide 12 from the evals run; compute slide 10 cost; add slide 14 links once deployed. |
| Oct 18 morning | Export PDF, check every placeholder is gone, submit with time left for a failed upload. |

## Open items

1. Team leader and member list (slide 1). Team name is set: NeuralNodes.
2. Final Gemini model name (slide 9).
3. Cost figures (slide 10) after deployment.
4. All measured results (slides 11, 12) and links (slide 14).
5. Whether to delete slide 2 and the empty slides 15–16.
