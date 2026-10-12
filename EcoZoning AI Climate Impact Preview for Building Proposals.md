# EcoZone AI: Climate Impact Preview for Building Proposals

Oct 12, 2026 · @Abhishek Sirohi

EcoZoning AI lets a city planner select a parcel, enter a proposed building, and see how ventilation, heat exposure and green connectivity change. Gemini then searches for better designs, and an area view shows what happens when every vacant parcel on a street is built out. The heat index is checked against satellite surface temperature. Built for the Google Cloud AI Builder Cup 2026 (Sustainability & Social Impact); prototype due Oct 18, 2026.

## Problem statement

Building proposals in fast-densifying cities are checked against fixed rules, and never against what they do to the airflow and heat of the blocks around them.

In Pune and other JAPAC cities, a proposal is checked against height limits, floor-area ratio and setbacks. None of these ask whether the building blocks the breeze that cools the blocks behind it, or replaces soil and trees with surfaces that hold heat. A fully legal building on the wrong plot can therefore make a neighborhood hotter.

### Who pays

Outdoor workers, the elderly and children are the people who cannot buy their way out of heat. They cannot rely on air conditioning, and they bear the exposure when a street loses its breeze. The harm is also hard to undo: once a natural cooling corridor is built over, it cannot be restored.

### The decision gap

Planners can see what exists today, but they cannot easily ask what changes if a specific building goes on a specific parcel. Detailed microclimate studies exist, but they are specialist work, so most proposals never get one. Cities ask "Can we build here?" and not "What happens to the neighborhood if we build here?"

### Why it compounds

Hotter streets raise cooling demand, while dense building reduces natural ventilation and increases heat retention. Each effect feeds the other, so a small loss of airflow on a key parcel can have a wide and lasting cost.

### The evidence

- India recorded between 10,545 and 20,615 heat deaths from 2000 to 2020, depending on the agency counting (IMD, NDMA or NCRB); experts say the true toll is higher ([Dialogue Earth via PreventionWeb](https://www.preventionweb.net/news/indian-cities-struggle-plan-heat-most-vulnerable-suffer), Apr 2026).
- About 57% of Indian districts, home to over three-quarters of the population, are at high or very high heat risk (CEEW 2025, reported in the same article).
- City heat action plans, India's main response, centre on warnings, rehydration and medical teams once a heatwave is declared. Experts quoted in the same article call for long-term planning, green space and zoning clarity.
- In Pune, built-up area grew from 44.8% to 55.17% of the city between 2012 and 2023, and heat islands appeared at four of six study sites ([Tiwari et al., 2025](https://archives.christuniversity.in/items/show/23402)).

## Proposed solution

EcoZoning AI is a decision-support copilot that gives a planner a climate impact preview and ranked better designs for a proposed building in about a minute, and shows the cumulative effect when a whole street builds out. It never approves or denies a permit; it shows evidence and options.

1. The planner selects a parcel on the map of the frozen demo area.
2. The planner enters the proposed building: height in floors, footprint percentage, green or open-space percentage, and orientation.
3. The scoring engine computes baseline and proposed values for three indices, each on a 0 to 100 scale: Ventilation Corridor Index, Heat Exposure Index and Green Connectivity Score.
4. Gemini explains which factors drove the change, using only values returned by the engine.
5. Gemini searches for better designs: it proposes candidate envelopes, the engine scores each one, and Gemini refines the candidates until it can rank three options with their trade-offs.
6. The planner reads a short planning brief that lists the evidence and the recommended option.
7. For the cumulative effect, the planner switches to Area build-out, applies one envelope to every vacant parcel along a street, and sees how the whole area's scores change.

### The three options

| Option | What it optimizes | Rule |
| --- | --- | --- |
| A: Developer maximized | Floor area | The proposal as entered |
| B: Balanced | Climate score while keeping most of the floor area | Best candidate that keeps at least a set share of option A's floor area |
| C: Climate optimized | Climate score | Best candidate above a minimum development floor, so the answer is never simply "do not build" |

Floor area is footprint percentage times floors, used as a simple proxy for development value. The share kept in option B is a planner-adjustable setting.

### What it is not

It is not a computational fluid dynamics model and does not predict degrees or wind speeds. The three indices are screening indicators for comparing scenarios on the same parcel, and the interface says so. It is also not a permit authority: the planner decides.

### Who uses it, and when

Indian building permits are checked against fixed rules, and no step asks for a climate assessment today. The tool is therefore not pitched as a new mandatory approval step. It fits three moments that already exist:

- Large projects and layouts, where a planner can ask for a better design before approval.
- Development plan revisions, where the build-out view shows what the proposed limits would do to an area.
- Making the case for a rule, such as a height cap or a minimum green share along a cooling corridor.

### How it differs from existing tools

Professional tools such as [Autodesk Forma](https://www.autodesk.com/products/forma/environmental-impact-analysis) already offer wind and microclimate analysis, but they are paid subscriptions aimed at architects in early design. EcoZoning AI is aimed at the official reviewing a proposal or a plan: free public data, a one-minute screening, plain-language explanations and AI design search. It complements a detailed study on a large project; it does not replace one.

## High-level approach and design

The solution has two halves. An offline pipeline turns public data into one table of parcels per city, and a live app answers the planner through Gemini agents that call a deterministic scoring engine. A separate check compares the heat index with satellite surface temperature, so the scores come with evidence.

&#91;embedded content: high-level approach · data to three planner modes\]

Read it top down: data enters once per city, and every question after that goes through the engine, the only place a score is computed. The dashed path is evaluation only and never feeds a score.

| Mode | Planner gives | Engine computes | Gemini adds | Output |
| --- | --- | --- | --- | --- |
| Preview and explain | A parcel and a proposal: floors, footprint %, green %, orientation | Baseline and proposed VCI, HEI and GCS, risk label, driver tags | The drivers in plain words; imagery observations labeled AI-estimated | Before and after, risk label, a short explanation |
| Design search | The proposal and the share of floor area to keep | Scores for every candidate Gemini proposes | Proposes, compares and refines candidates for up to 3 rounds | Options A, B and C with their trade-offs |
| Area build-out | A street or group of blocks and the maximum envelope the rules allow | Rescores every parcel in the area, neighbors included | Names the parcels and streets that lose most, and why | Area averages before and after, count of HIGH parcels |

Every mode ends in the same planning brief, and every answer passes the output guard before the planner sees it.

## System architecture

The planner app talks to an agent layer, the agents call tools backed by the scoring engine, and the engine reads preprocessed data; Gemini never computes a score.

&#91;embedded content: system architecture · 4 layers, 1 guard\]

Requests flow down from the planner app and every answer returns through the output guard. The agents reach data only through the engine's tools, and the engine is the only place a score is computed.

## Scoring engine

The engine turns a parcel and a proposed building into three 0 to 100 indices using plain code over geometry and preprocessed data layers. Gemini's imagery observations can enter only as labeled inputs; the arithmetic itself never involves a model.

### Ventilation Corridor Index (VCI)

Higher means air can pass through the corridor around the parcel. A proposal lowers it by lengthening the built run, raising the building against the street width, and turning the building across the wind.

```latex
VCI = 0.30\,W_a + 0.25\,C_o + 0.25\,O_b + 0.20\,P_g

W_a = \max(0,\ 100\cos\Delta\theta) \qquad C_o = \max\left(0,\ 100 - \frac{L_{built}}{5}\right)

O_b = 100\left(1 - \min\left(1,\ \frac{H/W}{2.5}\right)\right) \qquad P_g = \max\left(0,\ 100 - \frac{d_{water}}{10}\right)
```

### Heat Exposure Index (HEI)

Higher means more heat retention. A proposal raises it by adding impervious surface, removing vegetation and adding building mass.

```latex
HEI = 0.40\,I_s + 0.35\,(100 - G_c) + 0.25\,T_m

T_m = 100\,\min\left(1,\ \frac{V}{V_{ref}}\right)
```

### Green Connectivity Score (GCS)

Higher means more green cover nearby that is also linked into a network. A proposal lowers it by removing green cover or leaving the remaining green cut off from existing patches.

```latex
GCS = 0.5\,G_{buf} + 0.5\,L_{link}

L_{link} = \max\left(0,\ 100 - \frac{d_{green}}{3}\right)
```

### Terms and what the proposal changes

| Term | Meaning | Source | Changed by the proposal |
| --- | --- | --- | --- |
| Δθ | Angle between the prevailing seasonal wind and the building's long axis (baseline: the street canyon axis) | Seasonal wind averages; OSM street geometry | Yes, through the orientation setting |
| L\_built | Longest unbroken built-up run along the wind line through the parcel, within 300 m | OSM buildings | Yes, adds footprint depth times footprint share |
| H, W | Building height (floors times 3 m) and adjacent street width; baseline H is the neighbors' average | OSM floors tag, road-class widths | Yes |
| d\_water | Distance to the nearest upwind park or water body | OSM | No |
| I\_s, G\_c | Impervious share and vegetation share, area-weighted over a 150 m buffer | Land cover, vegetation index | Yes, the parcel's share is replaced by footprint, paved remainder and green percentage |
| V, V\_ref | Building volume (footprint area times height) and the area's 95th-percentile building volume | OSM | Yes |
| G\_buf | Green share within 300 m after the proposal | Land cover | Yes |
| d\_green | Distance from the nearest existing green patch to the proposal's green area | OSM, land cover | Yes; shorter when green is placed as a connected corridor on the edge facing that patch |

Assumptions made explicit: 3 m per floor; street widths come from the road class where OSM has none; whatever is neither footprint nor green is treated as paved.

### Risk label

The worst change is the largest of the VCI drop, the HEI rise and the GCS drop. A worst change under 10 points is LOW, 10 to 24 is MODERATE, and 25 or more is HIGH. These thresholds are prototype settings, tuned on the test parcels on day 5.

> The indices are prototype composite indicators for comparing scenarios on the same parcel. They are not airflow or temperature measurements, and the weights are design heuristics. The heat index is checked against measured surface temperature (see Trust and evaluation); the other two indices are not validated.

### Area build-out

One building rarely changes a neighborhood; many buildings together do. The build-out view applies one envelope (floors, footprint %, green %) to every candidate parcel in a selected area at once, then rescores every parcel in that area. Built run, neighbors' heights and green buffers are computed from geometry, so each new building also lowers its neighbors' scores. That is how the cumulative effect appears.

- **Area:** a street segment or group of blocks the planner selects, capped at about 30 candidate parcels so a run stays fast (a prototype limit, measured on day 5).
- **Envelope:** typed in by the planner as the maximum the rules allow. Floor-area and height limits are not in the open data, so they are labeled as planner input.
- **Output:** the change and risk label for each parcel, the area average of each index before and after, the number of parcels whose worst change is HIGH, and how many existing blocks around them lose score.

## Gemini agents and tools

Gemini does the two jobs the engine cannot: it searches for better designs and it reads aerial imagery. Every design it proposes is scored by the engine, and every number it reports comes from a tool result.

### Agents

Three agents sit under one orchestrator, built with the Agent Development Kit. Each has its own tools, and the planner's request decides which are called.

| Agent | Job | Tools |
| --- | --- | --- |
| Orchestrator | Routes the request, calls the agents in order, enforces the output format | The three agents |
| Spatial Analyst | Gathers parcel context and imagery observations | get\_parcel\_context, analyze\_imagery |
| Scenario Analyst | Runs the proposal, the design search and the area build-out | simulate\_scenario, compare\_scenarios, simulate\_buildout |
| Planning Advisor | Explains drivers and writes the planning brief | format\_planning\_brief |

### Design search loop

This is the main Gen AI feature: Gemini proposes, the engine scores, Gemini refines.

1. Gemini receives the proposal, its baseline and proposed scores, and the planner's floor-area rule for option B.
2. Gemini proposes a batch of four candidate designs within the allowed ranges.
3. For each candidate it calls simulate\_scenario, and the engine returns scores and floor area.
4. Gemini discards candidates that break the floor-area rule and proposes a refined batch that moves in the direction that improved scores.
5. The loop stops after three rounds, or earlier when no candidate beats the best by more than 2 points.
6. Gemini selects options B and C from scored candidates only, then explains the trade-offs.

The levers are height in floors, footprint percentage, green percentage, orientation, and green placement (scattered, or a connected corridor on the edge facing the nearest green patch). Candidates may not exceed the proposal's height or footprint, may not reduce its green share, and may use orientation in 15 degree steps. These ranges and the loop limits are prototype settings.

In the build-out view, Gemini summarizes which parcels and streets lose most and why, using the engine's driver tags. If the Oct 16 gate passes early, the same loop can search area rules instead of single designs: Gemini proposes a height cap or a minimum green share, simulate\_buildout scores each, and Gemini reports the rule that keeps the most floor area for the least climate loss.

### Reading aerial imagery

For the selected parcel, Gemini receives a prepared aerial image of the parcel and its surroundings and returns structured observations: tree-cover share, paved share, roof share, notable open spaces, and a confidence level (low, medium or high) for each. Four rules govern what happens next.

- Data layers stay primary. Imagery never silently overrides them.
- When imagery and a data layer differ by more than 15 points, the planner sees both values and a disagreement flag.
- When a data layer is missing for the parcel, such as a missing floors tag, the imagery estimate fills the gap and is labeled AI-estimated with its confidence.
- Observations are saved with the scenario so the explanation can cite them.

### Grounding rules for every explanation

- Every number comes from a tool result in the same turn.
- No physical units: no degrees Celsius, no meters per second, no kilowatt-hours.
- The agent never approves or denies a proposal; it presents options and a recommendation.
- AI-estimated values are always labeled as such.
- Output has fixed parts: diagnosed impact, primary drivers, options and trade-offs, recommendation, data caveats.

Primary drivers are computed by the engine, not by Gemini: for each index, the engine names the term whose weighted change contributed most (for example OBSTRUCTION, BUILT\_RUN, IMPERVIOUS\_GAIN, MASS\_GAIN, GREEN\_ISOLATED). Gemini explains them in plain language.

### Tool contracts

| Tool | Inputs | Returns |
| --- | --- | --- |
| get\_parcel\_context | parcel id | Centroid, area, baseline indices, canyon axis, data-gap flags |
| analyze\_imagery | parcel id | Structured observations with a confidence per field |
| simulate\_scenario | parcel id, floors, footprint %, green %, orientation, green placement | Baseline and proposed indices, deltas, driver tags, floor area, risk label |
| compare\_scenarios | parcel id, scenario ids | Ranked table of scenarios by climate score and floor area |
| simulate\_buildout | area id or parcel ids, floors, footprint %, green % | Per-parcel deltas and risk labels, area averages before and after, count of HIGH parcels, driver tags |
| format\_planning\_brief | parcel id, scenarios, selected option | Structured brief: summary, risk label, recommendation, caveats |

## Data pipeline

All data is prepared once, ahead of the demo, from open sources. The app reads preprocessed tables and never processes satellite rasters while a planner waits.

### Sources

| Layer | Source | Access | Used for | Known limit |
| --- | --- | --- | --- | --- |
| Buildings, roads, parks, water | OpenStreetMap | Overpass API, no account | Geometry, street width, canyon axis, distances to water and green | Small green patches and street widths often missing |
| Building heights | [Google Open Buildings 2.5D Temporal](https://sites.research.google/gr/open-buildings/temporal), 2023 layer | Earth Engine; CC BY 4.0 or ODbL | H and building volume wherever OSM has no floors tag | About 4 m effective resolution, capped at 100 m; accuracy measured outside India only, so labeled as estimates |
| Vegetation and built-up indices | Sentinel-2 surface reflectance | Earth Engine, `COPERNICUS/S2_SR_HARMONIZED` | Vegetation share (NDVI) and built-up share | 10 m; needs a cloud-free dry-season composite |
| Land cover classes | [ESA WorldCover](https://registry.opendata.aws/esa-worldcover-vito/index.html) 10 m, 2021 | Earth Engine, `ESA/WorldCover/v200` | Impervious and green shares, cross-check of the indices | 2021 snapshot; misses recent construction |
| Prevailing wind | [Open-Meteo](https://open-meteo.com/) historical weather API (ERA5) | HTTP, no key, free for non-commercial use | Dominant wind direction for the chosen season | Coarse grid; one direction for the whole area |
| Surface temperature (validation only) | Landsat 8 and 9, Collection 2 Level 2 | Earth Engine | Checking the heat index against measurement | Daytime overpass; surface, not air, temperature |
| Images for Gemini | Sentinel-2 true-color and vegetation false-color clips | Earth Engine thumbnails, shipped with the app | analyze\_imagery input | 10 m; trees show as patches, not single trees |

Google Maps satellite tiles are not used: the [Maps Platform terms](https://cloud.google.com/terms/maps-platform/maps-analytics-service-terms) bar using Maps content to train, test or validate AI models, and that wording is too broad to risk in a public, judged entry.

### Preprocessing job

1. **Get access.** Register a Google Cloud project for Earth Engine as noncommercial. The default Community tier gives 150 compute-hours a month at no charge ([tiers](https://developers.google.com/earth-engine/guides/noncommercial_tiers)), far more than one area needs. Do this first; every satellite step depends on it.
2. **Choose the area.** For the Shivajinagar and Kothrud bounding boxes, compare the share of buildings with a height from either an OSM floors tag or Open Buildings. Freeze the box with better coverage.
3. **Extract.** Pull buildings, roads, parks and water from Overpass for a box of about 2.5 km by 2.5 km.
4. **Define parcels.** OpenStreetMap has no cadastral parcels, so a parcel is a block formed by the road network, offered as a candidate when its building coverage is low or it is tagged vacant or open.
5. **Add satellite layers in Earth Engine.** For each footprint, take the OSM floors tag times 3 m, else the Open Buildings height. For each block, take a dry-season Sentinel-2 median (vegetation and built-up shares), WorldCover shares, and the median summer Landsat surface temperature from cloud-free scenes.
6. **Get the wind.** Pull hourly wind direction for Pune from Open-Meteo for recent years and take the dominant direction for the chosen season.
7. **Compute attributes.** For each parcel: area, neighbors' average height, street width, canyon axis, built run along the wind line, distances to water and green, buffer shares, and the area's reference building volume.
8. **Score and validate.** Run the engine on every block with no new building, store the three baseline indices and data gaps, and compute the heat index against surface temperature (see Trust and evaluation).
9. **Prepare images.** Export a true-color and a vegetation false-color clip per candidate parcel for Gemini.
10. **Load.** Write the parcel table to BigQuery with GEOGRAPHY columns, directly from Earth Engine or through a CSV in Cloud Storage; ship the image clips with the app.

### Where data lives

| Store | Holds | Why |
| --- | --- | --- |
| BigQuery | Parcel table, geometry, attributes, baseline indices | Spatial lookups with ST\_DWithin and ST\_Intersects |
| Firestore | Scenarios, design-search candidates, imagery observations, conversation state | Fast reads and writes per session |
| Cloud Run container | Engine, agents, frontend, demo image tiles | One deployable unit |

### Repeatable for any city

Onboarding a new city means changing the bounding box, the wind direction and the road-class width defaults, then running the same job. No engine or agent code changes. This is the scalability claim, and it is only made for the demo area until a second city is actually run.

### Open items to settle on day 1

- Earth Engine noncommercial eligibility for a hackathon entry: read the eligibility terms while registering. If it is refused, use Copernicus Data Space for Sentinel-2 and skip Landsat validation.
- Prevailing wind direction and season: verify against the downloaded data before it is fixed in the engine.
- Open Buildings heights in the frozen area: spot-check about 10 buildings against OSM floors tags or the image clips.
- If the satellite steps miss the Oct 14 gate, fall back to OSM land-use proxy indices and OSM-only heights with storey defaults, labeled as defaults.

## Experience and demo flow

The product is one screen with one flow: select a parcel, enter a building, see before and after, then find better designs. The 3-minute video follows the same path without cuts.

### The screen

| Area | Contents |
| --- | --- |
| Map (left) | Candidate parcels, the selected parcel highlighted, the proposed building shown on it |
| Parcel analysis (right, top) | Baseline Ventilation, Heat Exposure and Green Connectivity as labeled bars, with a one-line tooltip each |
| Development inputs | Sliders for height, footprint and green share, an orientation control, and a Preview impact button |
| Before and after | Baseline against proposed for each index, with the change shown as an arrow and a number, plus the risk label |
| Explain | Gemini's explanation: diagnosed impact, primary drivers, caveats |
| Find better designs | Live progress of the design search, then three option cards (A, B, C) with scores, share of floor area kept and a one-line trade-off; Apply option loads it into the sliders |
| Area build-out | Select a street or blocks on the map, set the maximum envelope, and see each parcel colored by its risk label, area averages before and after, and Gemini's summary of what loses most |
| Data badges | AI-estimated and disagreement flags next to any value that needs them |

Showing the design search as it runs, with candidates appearing and being scored, is the visible agentic moment of the demo.

### Usability and accessibility

- Change direction is shown with text and arrows as well as color, so it reads without color vision.
- Sliders and buttons are keyboard operable and have visible labels.
- Plain language throughout; each index has a one-sentence definition on hover or focus.
- Every Gemini statement can be traced to a number on screen.

### The 3-minute video

| Time | On screen | Message |
| --- | --- | --- |
| 0:00 to 0:25 | Title, then the map | Cities ask whether a building is allowed, not what it does to the neighborhood; outdoor workers, the elderly and children pay |
| 0:25 to 0:55 | Select a parcel | Baseline indices, imagery observations and a data flag |
| 0:55 to 1:35 | Enter a tall, large-footprint proposal and preview impact | Before and after, risk label, then Explain with named drivers |
| 1:35 to 2:10 | Find better designs | The loop runs; options A, B and C appear; apply B and show the change |
| 2:10 to 2:35 | Area build-out on one street | Every vacant parcel built to the maximum; area scores fall and HIGH parcels appear, including on existing blocks |
| 2:35 to 3:00 | Architecture and heat-check slide | Every score is computed by the engine, the heat index is checked against satellite measurement, AI-estimated inputs are labeled, one job onboards a city |

Do not write any scores into the script in advance. Pick the demo parcel from the test parcels on day 5, record from real output, and keep a backup recording.

## Trust and evaluation

Trust rests on one rule that code and tests enforce: every number shown comes from the engine, and any AI-estimated input is labeled.

### How the rule is enforced

- Gemini's only numeric sources are the engine tools; it has no tool that returns free-form figures.
- An output guard checks each explanation before it is shown. It rejects any number that does not appear in that turn's tool results and any forbidden unit. A rejected answer is regenerated once; if it fails again, the planner sees a plain template built from the engine values.
- AI-estimated values carry a visible label and confidence wherever they appear, including in the brief.

### Tests

Tests live in an evals folder in the repository. Results are measured and reported in the README; targets are not claimed before they are run.

| Test | What it checks | Passes when |
| --- | --- | --- |
| Determinism | The same inputs give the same scores | Ten repeated runs match exactly |
| Range | Indices stay within 0 to 100 | Holds on all test parcels, including a wide riverfront plot, a dense interior block and an isolated corner plot |
| Direction | More height or footprint never improves ventilation or lowers heat exposure; more green never raises heat exposure or lowers connectivity | Holds across a sweep of settings on each test parcel |
| Grounding | Explanations contain only numbers from tool results and no forbidden units | Zero violations on all test runs |
| Tool use | The agent fetches context and simulates before explaining | Reported as a success rate over ten parcels |
| Design search | Options B and C come from scored candidates; B keeps the floor-area share; C beats A on climate score | Holds on each test parcel |
| Speed | Engine time per scenario, time to preview, time for the design search | Measured and reported; the search returns its best result so far at a time limit |
| Heat check | Baseline heat index ranks blocks the way measured surface temperature does | Rank correlation and block count reported on held-out blocks; no pass mark |

### Checking the heat index against measurement

The heat index is the one score public data can check, so the prototype checks it and reports the result whatever it is. Ventilation and green connectivity have no open measurement to compare against.

1. Compute the baseline heat index for every block in the demo area, with no new building.
2. Take each block's median land surface temperature from cloud-free Landsat 8 and 9 scenes in the pre-monsoon months (March to May).
3. Split the blocks at random into two halves; weights may be tuned on the first half only.
4. Report the rank correlation (Spearman) and the block count on the second half, with a scatter plot in the deck.

Two caveats travel with the number. Surface temperature is not the air temperature people feel. And the index shares inputs, the paved and green shares, with what drives surface temperature, so a good result shows the index ranks blocks the way measured heat does, not that its weights are right. Temperatures appear only in this check, never in a planner-facing output.

### What we will not claim

- Any temperature, wind speed or energy figure in a planner-facing output (surface temperature appears only in the heat-index check).
- Fluid dynamics modeling.
- Long-range forecasts.
- Permit approvals or denials.
- Results for any city other than the demo area until a second city is actually run.

### Limits stated openly

- The indices are heuristic screening indicators. Only the heat index is checked, and only against surface temperature; ventilation and green connectivity are not validated against airflow studies or field data.
- OpenStreetMap completeness varies; missing heights come from Open Buildings estimates, whose accuracy has not been measured in India.
- Parcels are road-network blocks, not legal plots.
- Wind is a seasonal prevailing direction, not a wind field.

The path beyond the prototype is to validate and calibrate the indices with a partner who can supply measurements or detailed studies for the same area, and to run a second city through the pipeline.

## Six-day plan

The plan works only if weekday evenings finish the data, the engine and a first agent loop, and the weekend carries integration, deployment and the submission pack.

Weekday evenings give about 15 to 30 person-hours in total (3 builders, 1 to 2 hours, 5 evenings), so the weekend is where most of the build is finished. A suggested split is one builder each on data and engine, agents, and the app, with everyone joining the submission pack on the weekend. Deploy an empty version of the app to Cloud Run on Oct 13 so the deployment path is proven early.

&#91;embedded content: six-day plan · 5 lanes, 4 gates\]

| Gate | Day | Passes when | If it fails |
| --- | --- | --- | --- |
| Engine on real parcels | Oct 14 | Indices are computed for real parcels in the frozen area, the range and determinism tests pass, and the heat check has a first number | Switch to OSM proxy indices at once; do not wait |
| Full flow works | Oct 16 | Select, simulate, explain, design search and area build-out work end to end locally | Cut the design search to one round of proposals and keep the loop code behind a setting |
| Feature freeze | Oct 17 | Deployed on Cloud Run, evals run, demo parcel chosen | Stop adding features; fix only what breaks the demo |
| Submit | Oct 18 | Live link, repository, video and deck all submitted | Submit in the morning and leave time for a failed upload |

### If time runs short

1. Satellite indices become OSM proxy indices (decided in the interview). The heat check is then skipped and listed as future work.
2. Design search rounds drop from three to one (suggested).
3. Area build-out runs on one prepared street instead of any selected area (suggested).
4. UI polish is reduced while the logic and the demo path are kept (suggested).

## Locked decisions

Every choice below was made in the planning interview or the Oct 12 problem review and is fixed for the build; a change needs a reason tied to the Oct 18 deadline.

| Decision | Locked choice | Reason |
| --- | --- | --- |
| Competition and theme | Google Cloud AI Builder Cup 2026, Sustainability & Social Impact | The theme names resilience and informed decision-making explicitly |
| Deadline | Oct 18, 2026 (6 days left) | Official timeline; evaluation runs Oct 19 to Nov 6 |
| Team capacity | 3 builders, 1-2 hours on weekday evenings, heavy weekend work | Sets the scope; the weekend carries deployment, video and deck |
| Primary user | City planners and municipal officials | One user keeps the story and the interface simple |
| Core hook | Climate impact preview before a permit | One sentence judges can repeat |
| People at risk | Outdoor workers, the elderly, children | Names who pays when a cooling path is lost |
| Role of Gemini | Design search (propose, score, refine) and reading aerial imagery | Carries the 40% Gen AI criterion and the 25% innovation criterion |
| Data | Real OpenStreetMap geometry plus real satellite-derived indices, with Open Buildings heights where OpenStreetMap has none, preprocessed ahead of time | Credibility with technical judges; no live raster processing |
| Imagery rule | Data layers are primary; Gemini observations cross-check them and fill gaps, labeled AI-estimated with a confidence flag; disagreements are shown to the planner | Keeps decisions correct and the trust story honest |
| Scalability story | Repeatable city pipeline: one preprocessing job onboards a new city | Answers the scalability sub-criterion with something buildable |
| Evidence for impact | Public sources only | No access to a planner contact in the window |
| Demo area | Shivajinagar or Kothrud, whichever has more buildings with a height from OpenStreetMap or Open Buildings; decided on day 1 | The engine depends on building heights |
| Cut order | Satellite indices first (fall back to OSM proxy indices), then everything else only if needed | Protects the Gemini features that score |
| Where it fits | Large projects, development plan revisions and the case for a rule; not a new mandatory permit step | No permit step asks for a climate assessment today |
| Cumulative view | Area build-out: one envelope on every candidate parcel in a selected area, every parcel rescored | Answers the objection that one building changes nothing |
| Validation | Heat index checked against Landsat surface temperature on held-out blocks; result reported whatever it is | Gives the 40% technical criterion evidence, not only labels |

## Judging criteria and submission

The design targets all four weighted criteria; the table shows how, and what has to exist at submission to prove it.

| Criterion (weight) | How the design meets it | Proof to show |
| --- | --- | --- |
| Technical Merit and Gen AI Implementation (40%) | Gemini runs a propose, score, refine design search and reads imagery through tools; a tested engine does the arithmetic; deployed on Cloud Run; one job onboards a new city | The search running in the demo, the evals folder with measured results, the heat-check result, a live URL |
| Problem Alignment and Impact (25%) | Names a real decision gap and the groups that pay for it; matches the theme's focus on resilience and informed decisions | The evidence list in the problem section, with public sources |
| Innovation and Creativity (25%) | A climate preview before a permit, and AI design search scored by an engine, rather than a chatbot over a map; an area build-out that shows the cumulative effect; transparent AI-estimated data | The demo flow and the trust statement |
| User Experience and Solution Design (10%) | One screen, one flow, change shown in text and arrows as well as color, visible agent progress | The demo video and the live app |

### Submission checklist

These are the mandatory items on the official competition pages.

- [ ] Working prototype deployed on Cloud Run or Firebase, opening without a login
- [ ] Public GitHub repository, created during the hackathon, with no keys in the code
- [ ] Demo video under 3 minutes, as a public YouTube, Vimeo or Drive link
- [ ] Deck exported as a PDF covering problem, solution, feasibility and scalability
- [ ] Theme stated as Sustainability & Social Impact
- [ ] All materials in English
- [ ] One solution under one theme; every member a working professional, 21 or older, based in JAPAC
- [ ] Team of 2 to 4 confirmed as registered (the site shows registration closed on Oct 11 while its timeline lists team formation to Oct 14; email support if unsure)
- [ ] Gemini model name checked against the current Google Cloud model list before coding
- [x] 2 or 3 public sources added to the problem section (urban heat, ventilation and planning rules)

## Sources

Competition rules, timeline, themes, judging criteria and submission requirements were read from the official pages on Oct 12, 2026.

- [AI Builder Cup 2026: overview and timeline](https://aibuildercup.com)
- [Challenges and requirements](https://aibuildercup.com/themes.html)
- [Rewards and prizes](https://aibuildercup.com/rewards.html)
- [FAQs](https://aibuildercup.com/Faqs.html)

The problem statement's public evidence on urban heat and planning rules is still to be added (see the checklist).
