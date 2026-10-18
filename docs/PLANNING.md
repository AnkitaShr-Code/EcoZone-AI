# EcoZone AI: Repair and Protect a City's Cooling Network

Oct 12, 2026 · updated Oct 13, 2026 · @Abhishek Sirohi · Team NeuralNodes

EcoZone AI helps a city cool the streets people already live and work on, and stops new buildings from undoing that work. In **Repair** mode, a planner selects an area, sets a rupee budget, and Gemini designs a mix of street trees, shade structures, depaving, pocket green and cool roofs. A deterministic engine scores every option, including how much footpath it shades in the hot afternoon hours. In **Protect** mode, the planner previews what a proposed building does to ventilation, heat and green connectivity, and Gemini searches for better designs. Both modes share one engine and one map. The heat index is checked against satellite surface temperature. Built for the Google Cloud AI Builder Cup 2026 (Sustainability & Social Impact); prototype due Oct 18, 2026.

Component-level design: [DESIGN.md](DESIGN.md). Task checklist: [TASKS.md](TASKS.md). Deck plan: [PITCH_DECK_PLAN.md](PITCH_DECK_PLAN.md).

## What changed on Oct 15

Build decisions taken before backend coding started; full list and reasons in [ENGINEERING_RULES.md](ENGINEERING_RULES.md#2-decisions-locked-on-oct-15).

| Decision | Choice |
| --- | --- |
| Demo area | Deccan Gymkhana – Fergusson College box, frozen (the area the UI is built on) |
| Earth Engine | Pending; OSM-only path built first, EE layers added as a new bundle version if approved |
| Building heights | OSM height, then OSM levels, then Open Buildings (if EE), then labeled typology defaults |
| Footpaths | 10 m chunks with a shaded flag per reference time |
| Area load | Versioned GeoParquet bundle on Cloud Storage; BigQuery holds an analytics copy |
| Agent routing | Plain code by API route; role-based agents and one shared search loop, built without ADK |
| Models | Flash tier for the search proposer, Pro tier for explanations and briefs |
| Protect preview | Live engine `rescore` at discrete slider levels; no precomputed lookup |

## What changed on Oct 13

The Oct 12 version was a permit-stage preview only. After a design review the team decided:

| Decision | Choice |
| --- | --- |
| Lead mode | **Repair** leads the pitch, the video and the app's default screen; Protect comes second |
| Interventions scored in the demo | Street trees, shade structures, depave and plant, pocket green, cool roofs |
| New index | Pedestrian Shade Score, computed from building heights and sun position |
| Front end | React + TypeScript with deck.gl and MapLibre; FastAPI backend |
| Area build-out | Kept in Protect; shares the area-rescoring engine with Repair |
| Repair budget | Rupees, using planner-entered unit costs |
| Vulnerability | Built-form proxy (dense low-rise blocks), named as a built form, never as a social label |
| Capacity | 100 to 130 person-hours for Oct 13 to 18 |
| Quick wins (Oct 15) | A planner-set share of the Repair budget (default 20%) must go to interventions that help this summer |
| Canopy on deep streets (Oct 15) | A site rule keeps dense tree rows off streets with height-to-width of 1 or more |

## Problem statement

Indian cities are getting hotter street by street. The people who wait outdoors have no shade, and the city has no quick way to decide where a limited budget for trees, shade or cool surfaces would help most. At the same time, new buildings that follow every rule can still block the breeze and pave over the green that cools a neighborhood.

### Who pays

Outdoor workers, street vendors, commuters at bus stops, the elderly and children are the people who cannot buy their way out of heat. They cannot rely on air conditioning, and they spend the hottest hours on footpaths, at bus stops, in markets and in school yards. People in dense low-rise housing under tin or concrete roofs also carry the heat indoors.

### The decision gap

Two questions have no easy answer today:

- **Repair:** "If we have ₹X this year, where would trees, shade, depaving or cool roofs help the most people, and which would backfire?"
- **Protect:** "If this building goes on this parcel, what happens to the neighborhood's breeze, heat and green?"

Detailed microclimate studies exist, but they are specialist work, so most wards and most proposals never get one. Heat action plans mostly respond once a heatwave is declared.

### Why it compounds

Hotter streets raise cooling demand, and dense building reduces natural ventilation and increases heat retention. Each effect feeds the other. The same paved surfaces that store heat also shed monsoon runoff, so the cost shows up in two seasons.

### The evidence

- India recorded between 10,545 and 20,615 heat deaths from 2000 to 2020, depending on the agency counting (IMD, NDMA or NCRB); experts say the true toll is higher ([Dialogue Earth via PreventionWeb](https://www.preventionweb.net/news/indian-cities-struggle-plan-heat-most-vulnerable-suffer), Apr 2026).
- About 57% of Indian districts, home to over three-quarters of the population, are at high or very high heat risk (CEEW 2025, reported in the same article).
- City heat action plans, India's main response, centre on warnings, rehydration and medical teams once a heatwave is declared. Experts quoted in the same article call for long-term planning, green space and zoning clarity.
- In Pune, built-up area grew from 44.8% to 55.17% of the city between 2012 and 2023, and heat islands appeared at four of six study sites ([Tiwari et al., 2025](https://archives.christuniversity.in/items/show/23402)).

## Proposed solution

EcoZone AI treats a neighborhood as one **cooling network** with three layers:

- **Air paths:** wide streets aligned with the prevailing wind, the river, nalas and open grounds.
- **Green patches and links:** parks, tree-lined streets, campuses, and the gaps between them.
- **Waiting points:** bus stops, markets, school gates, hospitals, where people spend time outdoors.

**Repair** completes the network where it is broken. **Protect** stops new buildings from breaking it. Both are decision support: the tool never approves, denies or orders work; it shows evidence and options, and the planner decides.

### Repair (lead mode)

1. The planner selects an area: the frozen demo area or a ward-sized part of it.
2. The map ranks blocks and footpaths by **priority**: heat exposure, lack of afternoon shade, waiting points nearby, and dense low-rise built form.
3. The planner sets a rupee budget, the share of it that must help this summer (quick wins), and checks the unit costs for each intervention type. Defaults are labeled planner input.
4. The engine lists candidate sites for each intervention type, using site rules (below).
5. Gemini runs the **portfolio search**: it proposes mixes of interventions within the budget, the engine scores each one, and Gemini refines. The engine also computes a simple greedy baseline, and the best of the two is shown.
6. The planner reads the plan: each intervention with its site, cost, the drivers that justify it, the waiting points it covers, its time to benefit, and its ventilation check. Rejected options are listed with the reason.
7. A shadow view shows footpath shade at 1, 3 and 4 pm on a reference April day, before and after.
8. The cooling plan brief phases the work (quick wins this summer, planting with the monsoon, multi-year canopy) and gives a field check list for each site.

### Intervention library

| Intervention | Site rule (prototype settings) | Engine terms changed | Backfires when | Time to benefit |
| --- | --- | --- | --- | --- |
| Street tree row | Footpath segment on a road with a width class that allows a planting strip, and height-to-width below 1; prefers east–west segments with low building shade | Shade (crown shadows), green share, green links | The street is deep and narrow (height-to-width 1 or more): canopy blocks the breeze and traps heat at night. The site rule keeps dense tree rows off these streets; the planner sees them as rejected (CANOPY_OBSTRUCTION) with a shade structure suggested instead | Years |
| Shade structure | Within 30 m of a waiting point (bus stop, market, school gate, hospital entrance) | Shade only | Monsoon wind load; needs maintenance and seasonal removal | Weeks |
| Depave and plant | Public paved open land: school yards, municipal parking, medians, traffic islands | Impervious share, green share, green links | Replaced with lawn that needs irrigation; prefer native shrubs and trees | One season |
| Pocket green | Vacant or amenity plot; scored higher when it closes a gap between existing green patches | Green share, green buffer, green links | Isolated scraps add little connectivity | 2 to 3 years |
| Cool roof | Buildings in dense low-rise blocks with low roof albedo | Roof albedo term in the heat index | Glare onto taller neighbours; coatings wear and need renewal | Weeks |

Greening nala and river edges is a vision item, not scored in the prototype.

### Protect (second mode)

1. The planner selects a parcel on the map.
2. The planner enters the proposed building: height in floors, footprint percentage, green or open-space percentage, and orientation.
3. The engine computes baseline and proposed values for the Ventilation Corridor Index, Heat Exposure Index, Green Connectivity Score and Pedestrian Shade Score.
4. Gemini explains which factors drove the change, using only values returned by the engine.
5. Gemini searches for better designs and ranks three options.
6. In **Area build-out**, the planner applies one envelope to every vacant parcel along a street and sees how the whole area's scores change.

| Option | What it optimizes | Rule |
| --- | --- | --- |
| A: Developer maximized | Floor area | The proposal as entered |
| B: Balanced | Climate score while keeping most of the floor area | Best candidate that keeps at least a set share of option A's floor area |
| C: Climate optimized | Climate score | Best candidate above a minimum development floor, so the answer is never simply "do not build" |

Floor area is footprint percentage times floors, a simple proxy for development value. The share kept in option B is a planner-adjustable setting.

### What it is not

- Not a computational fluid dynamics or thermal comfort model. It does not predict degrees or wind speeds. The indices are screening indicators for comparing options in the same area.
- The shade score is geometry: it says where shadow falls, not how cool it feels.
- Not a permit authority, a work order or a costing authority. Costs come from planner unit costs.

### Who uses it, and when

| User | Mode | Moment |
| --- | --- | --- |
| Ward office, tree or garden department, Smart City cell, a heat action plan cell where one exists | Repair | Annual budget planning in winter and spring; shade structures before the March to May heat; depaving in the dry season; planting with the monsoon in June and July |
| CSR and NGO partners funding greening | Repair | Choosing sites that help the most people per rupee |
| Planning department | Protect | Large projects and layouts, development plan revisions, making the case for a rule such as a height cap or minimum green share along a cooling corridor |

### How it differs from existing tools

- [Autodesk Forma](https://www.autodesk.com/products/forma/environmental-impact-analysis) offers wind and microclimate analysis as a paid tool for architects in early design.
- Tree equity tools such as American Forests' Tree Equity Score (United States) show where canopy is lacking, but do not design interventions, cost them or check them against ventilation.
- EcoZone AI designs a costed mix of five intervention types for a budget, checks each against ventilation and shade geometry, explains it in plain language, and uses free public data for Indian cities. It complements a detailed study on a large project; it does not replace one.

## High-level approach and design

An offline pipeline turns public data into tables per city in BigQuery. A live app answers the planner through Gemini agents that call a deterministic scoring engine; the engine is the only place a score is computed. A separate check compares the heat index with satellite surface temperature.

| Mode | Planner gives | Engine computes | Gemini adds | Output |
| --- | --- | --- | --- | --- |
| Repair: priority map | An area | Priority per block and footpath; baseline shade at 1, 3 and 4 pm | Names the top hotspots and why, from driver tags | Ranked hotspot map |
| Repair: cooling plan | Budget and unit costs | Candidate sites; score, cost and ventilation check for every portfolio; greedy baseline | Proposes and refines portfolios for up to 3 rounds; field check list per site | Costed, phased plan with before and after scores and shadows |
| Protect: preview and explain | A parcel and a proposal | Baseline and proposed indices, risk label, driver tags | Plain-language drivers; imagery observations labeled AI-estimated | Before and after, risk label, explanation |
| Protect: design search | The proposal and the share of floor area to keep | Scores for every candidate | Proposes and refines candidates for up to 2 rounds | Options A, B and C |
| Protect: area build-out | A street or group of blocks and the maximum envelope | Rescores every parcel in the area, neighbors included | Names the parcels and streets that lose most, and why | Area averages before and after, count of HIGH parcels |

Every mode ends in a brief, and every answer passes the output guard before the planner sees it.

## System architecture

React app → FastAPI service on Cloud Run → (deterministic API calls go straight to the engine; questions and searches go through the agent layer (plain asyncio code over `google-genai`, no ADK), whose tools call the engine) → area data loaded into memory from a GeoParquet bundle on Cloud Storage (BigQuery holds an analytics copy) → output guard on every Gemini answer. Sessions and plans are stored in Firestore, images and area bundles in Cloud Storage, and Gemini runs on Vertex AI with a service account, so there are no API keys in the code. Full component design: [DESIGN.md](DESIGN.md).

## Scoring engine

The engine turns an area, and a set of changes to it, into indices on a 0 to 100 scale, using plain code over geometry and preprocessed data layers. Gemini's imagery observations can enter only as labeled inputs; the arithmetic never involves a model.

### Ventilation Corridor Index (VCI)

Higher means air can pass through the corridor around the parcel or street.

```latex
VCI = 0.30\,W_a + 0.25\,C_o + 0.25\,O_b + 0.20\,P_g

W_a = \max(0,\ 100\cos\Delta\theta) \qquad C_o = \max\left(0,\ 100 - \frac{L_{built}}{5}\right)

O_b = 100\left(1 - \min\left(1,\ \frac{H/W}{2.5}\right)\right) \qquad P_g = \max\left(0,\ 100 - \frac{d_{water}}{10}\right)
```

Tree rows do not enter VCI. They are offered only on streets with height-to-width below 1, where canopy does not block the corridor; deeper streets are excluded by the site rule (see the intervention library).

### Heat Exposure Index (HEI)

Higher means more heat retention. The Oct 13 version adds a roof albedo term so cool roofs can be scored.

```latex
HEI = 0.35\,I_s + 0.30\,(100 - G_c) + 0.20\,T_m + 0.15\,R_a

T_m = 100\,\min\left(1,\ \frac{V}{V_{ref}}\right) \qquad R_a = 100\,\mathrm{clamp}\left(\frac{0.70 - \alpha_{roof}}{0.70 - 0.10},\ 0,\ 1\right)
```

### Green Connectivity Score (GCS)

Higher means more green cover nearby that is also linked into a network.

```latex
GCS = 0.5\,G_{buf} + 0.5\,L_{link}

L_{link} = \max\left(0,\ 100 - \frac{d_{green}}{3}\right)
```

### Pedestrian Shade Score (PSS)

Higher means more of the footpath is in shadow during the hot afternoon hours. It is computed from geometry only.

```latex
PSS_s = 100 \cdot \frac{1}{|T|}\sum_{t \in T} \frac{\text{shaded length of segment } s \text{ at } t}{\text{length of } s}
\qquad T = \{13{:}00,\ 15{:}00,\ 16{:}00\}\ \text{IST, 15 April}
```

Shadows come from buildings (length = height ÷ tan(sun altitude), cast away from the sun), tree crowns and shade structures. Footpaths are measured in 10 m chunks: a chunk counts as shaded at time *t* when its midpoint lies in shadow, so the shaded length of a run is the total length of its shaded chunks. The area PSS is the length-weighted mean of its chunks; a block's PSS is the length-weighted mean of the chunks bordering it.

### Repair priority and Area Cooling Score

Priority ranks where to act; it is a ranking, never shown as a measurement.

```latex
P_b = HEI_b \cdot \left(1 - \frac{PSS_b}{100}\right) \cdot E_b \cdot V_b

E_b = 1 + \min\left(2,\ \frac{\sum_{k \in \text{waiting points whose nearest point is within 150 m of the block boundary}} w_k}{3}\right) \qquad V_b = \begin{cases}1.25 & \text{dense low-rise}\\ 1.0 & \text{otherwise}\end{cases}
```

Waiting-point weights `w_k`: school 3, hospital 3, clinic 2, college 2, market 2, bus stop 1 (prototype settings). Dense low-rise: building coverage of 50% or more, median footprint 60 m² or less, median height 2 floors or fewer (prototype settings).

The **Area Cooling Score** is what the Repair search maximizes:

```latex
ACS = \frac{\sum_b w_b\,C_b}{\sum_b w_b} \qquad C_b = 0.45\,(100 - HEI_b) + 0.35\,PSS_b + 0.20\,GCS_b \qquad w_b = E_b\,V_b
```

Constraints: total cost within budget; at least the planner's **quick-win share** of the budget (default 20%) goes to interventions that help within weeks or one season (shade structures, cool roofs, depave and plant); and no block's VCI may drop by 10 points or more. Trees win on score per rupee but take years to give shade, so without the quick-win share a plan would leave this summer's heat untouched.

### Terms and what changes them

| Term | Meaning | Source | Changed by |
| --- | --- | --- | --- |
| Δθ | Angle between the prevailing seasonal wind and the building's long axis (baseline: the street canyon axis) | Open-Meteo; OSM street geometry | Protect: orientation |
| L\_built | Longest unbroken built-up run along the wind line, within 300 m | OSM buildings | Protect: footprint |
| H, W | Building height (floors × 3 m) and adjacent street width | OSM, Open Buildings, road-class widths | Protect: floors |
| d\_water | Distance to the nearest upwind park or water body | OSM | No |
| I\_s, G\_c | Impervious and vegetation share, area-weighted over a 150 m buffer | WorldCover, Sentinel-2 | Protect: footprint, green %; Repair: depave, pocket green, trees |
| V, V\_ref | Building volume and the area's 95th-percentile building volume | OSM, Open Buildings | Protect: floors, footprint |
| α\_roof | Area-weighted roof albedo in the 150 m buffer | Sentinel-2 broadband albedo estimate | Repair: cool roofs |
| G\_buf | Green share within 300 m | WorldCover | Protect: green %; Repair: green interventions |
| d\_green | Distance from the new green to the nearest existing green patch | OSM, WorldCover | Protect: green placement; Repair: pocket green, depave |
| Shadows | Building, crown and structure shadows at 13:00, 15:00, 16:00 | Heights + computed sun position | Protect: floors; Repair: trees, shade structures |

Assumptions made explicit: 3 m per floor; street widths come from the road class where OSM has none; footpaths are derived from road edges where OSM has no sidewalk geometry; whatever is neither footprint nor green is treated as paved; new tree crowns have a prototype diameter and height; roof albedo at 10 m is a block-level estimate, not a per-roof measurement.

### Risk label (Protect)

The worst change is the largest of the VCI drop, the HEI rise, the GCS drop and the PSS drop, measured on the block that contains the proposed building's parcel, not on the area as a whole: a building changes its own block, and averaging that change over every block of the area would hide a large drop on the one block it affects. With several proposed buildings, each parcel gets a label from its own block and the result carries the worst of them. A worst change under 10 points is LOW, 10 to 24 is MODERATE, and 25 or more is HIGH. These thresholds are prototype settings, tuned on the test parcels.

> The indices are prototype composite indicators for comparing options in the same area. They are not airflow, temperature or comfort measurements, and the weights are design heuristics. The heat index is checked against measured surface temperature (see Trust and evaluation); the other indices are not validated. The shade score is exact geometry under its stated assumptions, but says nothing about how cool the shade feels.

### Area rescoring (shared by Repair and build-out)

Both Repair and build-out change many things in one area at once, so one area-rescoring routine serves both. It applies a list of changes (new buildings, tree rows, shade structures, depaved or greened sites, cool roofs), recomputes the affected attributes and shadows, and rescores every block and footpath in the area, neighbors included.

- **Area size:** about 30 candidate parcels for build-out, about 200 blocks for Repair (prototype limits, measured for speed).
- **Build-out envelope:** the maximum the rules allow, typed in by the planner and labeled as planner input.
- **Output:** per-block changes, area averages before and after, count of HIGH parcels, and how many existing blocks lose score.
- **Waiting points covered:** a waiting point counts when a shade structure sits at it, or when footpath within 30 m of it is in the sun before and in shade after at 3 pm. Tree rows and other interventions count through the footpath they shade, so the number does not depend on the planner choosing shade structures.

## Gemini agents and tools

Gemini does the jobs the engine cannot: it searches for good portfolios and designs, it reads aerial imagery, and it explains. Every option it proposes is scored by the engine, and every number it reports comes from a tool result.

### Agents

Four agent roles, built as plain asyncio code over `google-genai` (the Agent Development Kit was evaluated and not used; see ENGINEERING_RULES.md), each with its own tools. Plain code picks the agent from the API route (decided Oct 15: the UI never sends free-form chat, so an LLM routing hop adds latency without value).

| Agent | Job | Tools |
| --- | --- | --- |
| Router (code) | Picks the agent by route, calls agents in order, enforces the output format | The four agents |
| Spatial Analyst | Area and parcel context, imagery observations | get\_area\_context, get\_parcel\_context, analyze\_imagery |
| Repair Planner | Hotspots, candidate sites, portfolio search | rank\_hotspots, list\_candidate\_sites, simulate\_interventions, greedy\_baseline |
| Scenario Analyst | Protect preview, design search, build-out | simulate\_scenario, compare\_scenarios, simulate\_buildout |
| Planning Advisor | Explanations, cooling plan, planning brief | format\_cooling\_plan, format\_planning\_brief |

### Portfolio search loop (Repair)

1. The Repair Planner receives the top hotspots, candidate sites (each with its cost and its single-site score gain) and the budget.
2. The engine computes a greedy baseline: fill the quick-win share with the best quick wins by score gain per rupee, then add the remaining sites by gain per rupee until the budget is spent.
3. Gemini proposes four portfolios per round. Its job is to find what greedy misses: interactions between sites. Two shade measures on the same footpath overlap, so the second adds little; depaving a school yard next to a pocket green links two patches, so together they add more than apart.
4. `simulate_interventions` scores each portfolio: ACS change, cost, ventilation check, waiting points covered, driver tags.
5. Gemini discards portfolios over budget, below the quick-win share or failing the ventilation check, and refines. The loop stops after two rounds, or earlier when no portfolio beats the best by more than 0.5 ACS points.
6. The best scored portfolio is shown. If the greedy baseline beats every Gemini portfolio, the app shows the greedy one and says so.

### Design search loop (Protect)

1. Gemini receives the proposal, its scores and the floor-area rule for option B.
2. It proposes four candidate designs within the allowed ranges.
3. Each is scored by `simulate_scenario`.
4. Candidates breaking the floor-area rule are dropped; Gemini proposes a refined batch.
5. The loop stops after two rounds, or earlier when no candidate beats the best by more than 2 points.
6. Options B and C are selected from scored candidates only.

Levers: height, footprint %, green %, orientation (15° steps), green placement (scattered, or a connected corridor on the edge facing the nearest green patch). Candidates may not exceed the proposal's height or footprint or reduce its green share.

### Reading aerial imagery

For a selected parcel or Repair site, Gemini receives prepared Sentinel-2 clips and returns structured observations (tree cover, paved share, roof share, open spaces) with a confidence level each.

- Data layers stay primary. Imagery never silently overrides them.
- When imagery and a data layer differ by more than 15 points, the planner sees both and a disagreement flag.
- When a layer is missing, the imagery estimate fills the gap, labeled AI-estimated with its confidence.
- 10 m imagery cannot see footpath width, overhead wires or young trees, so for each Repair site Gemini writes a **field check list** for the ward engineer instead of claiming feasibility.

### Grounding rules for every answer

- Every number comes from a tool result in the same turn.
- No physical units of temperature, wind speed or energy.
- Costs come only from planner unit costs, and are labeled as such.
- The agent never approves, denies or orders work.
- AI-estimated values are always labeled.
- Output has fixed parts: diagnosed issue, primary drivers, options and trade-offs, recommendation, data caveats.

Primary drivers are computed by the engine. Protect: OBSTRUCTION, BUILT\_RUN, IMPERVIOUS\_GAIN, MASS\_GAIN, GREEN\_ISOLATED, SHADE\_LOSS. Repair: SHADE\_GAIN, IMPERVIOUS\_LOSS, ALBEDO\_GAIN, GREEN\_LINK, CANOPY\_OBSTRUCTION, WAIT\_POINT\_COVERED.

### Tool contracts

| Tool | Inputs | Returns |
| --- | --- | --- |
| get\_area\_context | area id | Block count, baseline area indices, waiting points by type, data-gap flags |
| get\_parcel\_context | parcel id | Centroid, area, baseline indices, canyon axis, data-gap flags |
| analyze\_imagery | parcel or site id | Structured observations with a confidence per field; field check list for Repair sites |
| rank\_hotspots | area id, top n | Blocks and footpath segments by priority, with driver tags |
| list\_candidate\_sites | area id, intervention types | Sites with type, geometry id, quantity, cost, single-site ACS gain |
| simulate\_interventions | area id, list of (site id, type, quantity) | ACS before and after, per-block deltas, PSS before and after, cost, quick-win cost, ventilation check, waiting points covered, driver tags |
| greedy\_baseline | area id, budget, quick-win share | The greedy portfolio and its simulate\_interventions result |
| simulate\_scenario | parcel id, floors, footprint %, green %, orientation, green placement | Baseline and proposed indices, deltas, driver tags, floor area, risk label |
| compare\_scenarios | parcel id, scenario ids | Ranked table by climate score and floor area |
| simulate\_buildout | area id or parcel ids, floors, footprint %, green % | Per-parcel deltas and labels, area averages, HIGH count, driver tags |
| format\_cooling\_plan | area id, portfolio id | Phased plan: interventions, sites, costs, drivers, time to benefit, field check lists, caveats |
| format\_planning\_brief | parcel id, scenarios, selected option | Summary, risk label, recommendation, caveats |

## Data pipeline

All data is prepared once, ahead of the demo, from open sources. The app never processes satellite rasters while a planner waits.

### Sources

| Layer | Source | Used for | Known limit |
| --- | --- | --- | --- |
| Buildings, roads, sidewalks, parks, water | OpenStreetMap (Overpass / osmnx) | Geometry, street width, canyon axis, footpaths, distances | Small green patches, sidewalks and street widths often missing |
| Waiting points, public land | OpenStreetMap (bus stops, markets, schools, hospitals, parking, places of worship) | Exposure weights, candidate Repair sites | Coverage in Pune to be counted on day 1 |
| Building heights | [Google Open Buildings 2.5D Temporal](https://sites.research.google/gr/open-buildings/temporal), 2023 | Heights and volume where OSM has no floors tag; shadows; built-form class | About 4 m effective resolution; accuracy measured outside India only, so labeled as estimates |
| Vegetation and built-up | Sentinel-2 SR (`COPERNICUS/S2_SR_HARMONIZED`) | Vegetation share, built-up share | 10 m; dry-season composite |
| Roof albedo | Sentinel-2 SR bands, broadband albedo estimate over building pixels | α\_roof per block; cool-roof targeting | Block-level estimate; roofs smaller than a pixel are mixed with their surroundings |
| Land cover | [ESA WorldCover](https://registry.opendata.aws/esa-worldcover-vito/index.html) v200, 2021 | Impervious and green shares | 2021 snapshot |
| Prevailing wind | [Open-Meteo](https://open-meteo.com/) historical API (ERA5) | Dominant seasonal wind direction | One direction for the whole area |
| Sun position | Computed (pvlib) for the area centroid | Shadow geometry at 13:00, 15:00, 16:00 IST on 15 April | Clear-sky geometry; ignores haze and clouds |
| Surface temperature (validation only) | Landsat 8 and 9, Collection 2 Level 2 | Checking the heat index | Daytime surface temperature, not air temperature |
| Images for Gemini | Sentinel-2 true-color and false-color clips | analyze\_imagery | 10 m |
| Unit costs | Planner input, with labeled defaults | Portfolio cost | Not market prices |

Google Maps tiles and Street View are not used: the [Maps Platform terms](https://cloud.google.com/terms/maps-platform/maps-analytics-service-terms) bar using Maps content to train, test or validate AI models.

### Preprocessing job

1. **Get access.** Earth Engine noncommercial registration (applied; awaiting approval as of Oct 13).
2. **Choose the area.** Compare Shivajinagar and Kothrud by the share of buildings with a height and by the count of OSM waiting points. Freeze the better box.
3. **Extract OSM** for a box of about 2.5 km by 2.5 km.
4. **Build geometry.** Blocks from the road network; footpath segments from road edges (OSM sidewalks where present, otherwise offset from the centerline by half the road-class width), split into 10 m chunks.
5. **Classify.** Candidate parcels for Protect (low coverage or tagged vacant); candidate sites for Repair per the site rules; built-form class per block.
6. **Earth Engine layers.** Heights, Sentinel-2 shares, roof albedo, WorldCover shares, Landsat surface temperature, image clips.
7. **Wind and sun.** Dominant wind direction for the season; sun altitude and azimuth for the three reference times.
8. **Attributes and baselines.** Per-block attributes; baseline shadows and PSS per segment; baseline VCI, HEI, GCS, priority and ACS.
9. **Validate.** Heat check against surface temperature on held-out blocks.
10. **Load** tables to BigQuery with GEOGRAPHY columns; area bundles and image clips to Cloud Storage.

### Where data lives

| Store | Holds | Why |
| --- | --- | --- |
| BigQuery | Buildings, blocks, parcels, footpath segments, waiting points, candidate sites, baselines, validation, run logs | Spatial queries with ST\_ functions; one dataset per city; analytics on runs and evals |
| Firestore | Sessions, scenarios, portfolios and their scores, imagery observations, plans | Fast per-session reads and writes |
| Cloud Storage | Image clips, precomputed area bundles for the map, exported briefs | Cheap static files |
| In-memory (engine) | One area's geometry and attributes, loaded from the area bundle at startup | Each portfolio is scored in milliseconds, not one query per candidate |

### Repeatable for any city

Onboarding a city means changing the bounding box, the wind season, the road-class width defaults and the reference date, then running the same job. No engine or agent code changes. This claim is made for the demo area only until a second city is actually run.

## Experience and demo flow

One screen, a mode switch (Repair first), and one map.

| Area | Repair | Protect |
| --- | --- | --- |
| Map | Priority blocks; footpaths colored by shade; waiting points; 3D buildings; shadows with a time slider (1, 3, 4 pm); proposed interventions as icons | Candidate parcels; the proposed building in 3D; shadows |
| Inputs | Budget, unit costs, intervention types allowed | Floors, footprint, green share, orientation |
| Search | Live portfolio rounds, each scored as it arrives; greedy baseline shown alongside | Live design rounds; options A, B, C |
| Result | Plan table: site, type, cost, drivers, waiting points covered, time to benefit, ventilation check; rejected options with reasons | Before and after, risk label, explanation |
| Brief | Phased cooling plan with field check lists | Planning brief |
| Badges | AI-estimated, disagreement, planner input | Same |

### Usability and accessibility

- Change direction is shown with arrows and text as well as color.
- Map layers have text legends; priority classes are also labeled in words.
- Controls are keyboard operable with visible labels.
- Every Gemini statement can be traced to a number on screen.

### The 3-minute video

| Time | On screen | Message |
| --- | --- | --- |
| 0:00 to 0:20 | An east–west street at 3 pm, bus stop without shade | People wait in the heat; cities lack a way to decide where to fix it |
| 0:20 to 0:45 | Repair: priority map, shadows at 3 pm | Where heat, missing shade and waiting people overlap |
| 0:45 to 1:25 | Budget set; Gemini portfolio rounds run; plan appears; a dense tree row in a narrow lane is rejected for ventilation | AI designs the plan, the engine scores it, and it knows when trees backfire |
| 1:25 to 1:40 | Shadows before and after; cooling plan brief | Shade where people wait, phased by season |
| 1:40 to 2:20 | Protect: a large proposal on a vacant parcel; preview; options A, B, C | Don't undo the repair with the next building |
| 2:20 to 2:35 | Build-out on one street | The cumulative effect |
| 2:35 to 3:00 | Architecture, the evaluation report, Gemini vs greedy as measured | Every score from the engine; measured evals; the satellite check of the heat index as measured in REPORT.md (weak positive agreement on held-out blocks, stated plainly, not called validated); one job onboards a city |

Do not write any scores into the script in advance. Record from real output and keep a backup recording.

## Trust and evaluation

Trust rests on one rule that code and tests enforce: every number shown comes from the engine or from planner input, and any AI-estimated input is labeled.

### How the rule is enforced

- Gemini's only numeric sources are the engine tools.
- An output guard (a plain function applied to every model answer) rejects any number not present in that turn's tool results or planner inputs, and any forbidden unit. A rejected answer is regenerated once; if it fails again, the planner sees a plain template built from engine values.
- AI-estimated values and planner inputs carry visible labels wherever they appear.

### Tests

Tests live in `evals/`. Results are measured and reported in the README; targets are not claimed before they are run.

| Test | What it checks | Passes when |
| --- | --- | --- |
| Determinism | Same inputs give the same scores | Ten repeated runs match exactly |
| Range | Every index stays within 0 to 100 | Holds on all test areas and parcels |
| Direction (Protect) | More height or footprint never improves VCI or lowers HEI; more green never raises HEI or lowers GCS | Holds across a settings sweep |
| Direction (Repair) | Adding trees or shade never lowers PSS; depaving or cool roofs never raise HEI; adding green never lowers GCS | Holds for every intervention type on every test area |
| Shadow geometry | A test building of known height gives the expected shadow length and direction | Matches the formula within 1% |
| Ventilation site rule | No tree row is offered on a street with height-to-width 1 or more; such streets appear as rejected options with CANOPY_OBSTRUCTION | Holds on the test lanes |
| Budget and quick wins | Every shown portfolio is within budget and meets the quick-win share | Always |
| Gemini vs greedy | Gemini's best portfolio against the greedy baseline, same budget | Reported as win, tie or loss per test area; no pass mark |
| Grounding | Answers contain only numbers from tool results or planner input, and no forbidden units | Zero violations on all test runs |
| Tool use | The agent fetches context and simulates before explaining | Success rate over ten runs per mode |
| Design search | Options B and C come from scored candidates; B keeps the floor-area share; C beats A | Holds on each test parcel |
| Speed | Engine time per portfolio, per scenario; time to preview; search time | Measured and reported |
| Heat check | Baseline heat index ranks blocks the way measured surface temperature does | Spearman correlation and block count on held-out blocks; no pass mark |

### Checking the heat index against measurement

1. Compute the baseline heat index for every block, with no changes.
2. Take each block's median land surface temperature from cloud-free Landsat 8 and 9 scenes in March to May.
3. Split blocks at random into two halves; weights may be tuned on the first half only.
4. Report the Spearman correlation and block count on the second half, with a scatter plot in the deck.

Caveats that travel with the number: surface temperature is not the air temperature people feel; the index shares inputs with what drives surface temperature, so a good result shows ranking agreement, not that the weights are right. Landsat sees the top of a shade structure, not the shaded ground under it, so satellite data can never confirm that shade structures work.

### What we will not claim

- Any temperature, wind speed, comfort or energy figure in a planner-facing output.
- Fluid dynamics modeling or thermal comfort modeling.
- That a plan's cost is a market price.
- Permit decisions or work orders.
- Results for any city other than the demo area until a second city is run.

### Limits stated openly

- The indices are heuristic screening indicators; only the heat index is checked, and only against surface temperature.
- The shade score assumes clear sky and simple shapes; tree crowns are modeled as circles of a set size.
- OSM completeness varies; footpaths are derived where OSM has none; Open Buildings height accuracy has not been measured in India.
- Roof albedo at 10 m is a block-level estimate.
- Parcels are road-network blocks, not legal plots.
- Wind is a seasonal prevailing direction, not a wind field.
- Trees take years to give the canopy the plan assumes; the quick-win share keeps part of every plan working this summer.
- One proposed building barely moves the heat exposure index, because paving and green are averaged over a 150 m buffer; Protect's risk is usually driven by ventilation.

The path beyond the prototype: validate with a partner who can supply measurements, run a second city, and close the loop each year (plan in winter, plant with the monsoon, measure the next summer with Landsat, recalibrate).

## Build plan (Oct 13 to 18)

Capacity: 100 to 130 person-hours across three builders. Estimated scope: about 133 hours (see [DESIGN.md](DESIGN.md#6-effort-estimate)), at the top of that range, so expect the cut order below to trigger at least once.

| Lane | Owns |
| --- | --- |
| D: Data and engine | OSM pipeline, geometry, shadows, engine, greedy baseline, engine tests |
| A: Agents and cloud | Earth Engine layers, agent roles, tools, output guard, FastAPI, BigQuery loading, Cloud Run, agent evals |
| U: Front end | React app, deck.gl layers, panels, brief view, accessibility; helps with deck and video |

| Gate | Day | Passes when | If it fails |
| --- | --- | --- | --- |
| Engine on real data | Oct 14 | Blocks, footpaths and baseline indices including PSS exist for the frozen area; range and determinism pass | Switch to OSM proxy indices and default roof albedo at once |
| Both modes end to end | Oct 16 | Repair (priority, portfolio search, plan) and Protect (preview, design search, build-out) work locally | Cut search rounds to one; build-out to one prepared street |
| Feature freeze | Oct 17 | Deployed; evals run; demo area and parcel chosen | Fix only what breaks the demo |
| Submit | Oct 18 | Live link, repository, video and deck submitted | Submit in the morning |

### Cut order, only when a gate fails

1. Satellite layers become OSM proxy indices; roof albedo uses a labeled default; the heat check moves to future work.
2. Imagery reading shrinks to field check lists only.
3. Build-out runs on one prepared street.
4. Search rounds drop from three to one.
5. 3D building extrusion and visual polish.

Repair with all five interventions, the shade score, and the Protect preview are never cut.

## Locked decisions

| Decision | Locked choice | Reason |
| --- | --- | --- |
| Competition and theme | Google Cloud AI Builder Cup 2026, Sustainability & Social Impact | The theme names resilience and informed decision-making |
| Deadline | Oct 18, 2026 | Evaluation runs Oct 19 to Nov 6 |
| Team | NeuralNodes, 3 builders, 100 to 130 person-hours | Sets the scope |
| Lead mode | Repair, then Protect | Clear owner and budget; acts on land the city controls; strongest social-impact story |
| Primary users | Ward and tree or garden officials (Repair); planning department (Protect) | Two users of one map |
| Core hook | Repair and protect a city's cooling network | One sentence judges can repeat |
| People at risk | Outdoor workers, vendors, commuters, the elderly, children, people in dense low-rise housing | Names who pays |
| Interventions | Street trees, shade structures, depave and plant, pocket green, cool roofs | Covers shade, surfaces, green and roofs |
| Shade | Pedestrian Shade Score from heights and sun position | Shows the benefit people feel most, with geometry not guesswork |
| Role of Gemini | Portfolio search and design search (propose, score, refine); imagery reading; explanations | Carries the Gen AI and innovation criteria |
| Benchmark | Gemini's portfolio is compared with a greedy baseline | Shows the AI adds value, honestly |
| Budget | Rupees from planner unit costs, with a quick-win share (default 20%) that must help this summer | Lets Gemini trade between intervention types without leaving this summer's heat untouched |
| Canopy on deep streets | Site rule: no dense tree rows where height-to-width is 1 or more | One clear rule a planner can check on site |
| Vulnerability | Built-form proxy, labeled as built form | Targets cool roofs without stigmatizing labels |
| Data | Real OSM geometry, satellite-derived indices, Open Buildings heights, preprocessed | Credibility; no live raster processing |
| Stack | React + deck.gl + MapLibre; FastAPI; plain asyncio agent code on Vertex AI Gemini; BigQuery; Firestore; Cloud Storage; one Cloud Run service serving UI and API | Team skills cover all four areas; one URL, no proxy timeouts on live search streams |
| Imagery rule | Data layers primary; Gemini cross-checks and fills gaps, labeled AI-estimated | Keeps the trust story honest |
| Scalability | One preprocessing job per city | Buildable, not just claimed |
| Validation | Heat index against Landsat on held-out blocks, reported whatever it is | Evidence, not only labels |

## Judging criteria and submission

| Criterion (weight) | How the design meets it | Proof to show |
| --- | --- | --- |
| Technical merit and Gen AI (40%) | Two propose-score-refine searches over a tested engine; shade geometry; propose-score-judge agent roles with an output guard; Gemini vs greedy benchmark; deployed on Cloud Run | Live searches in the demo, evals with measured results, heat check, live URL |
| Problem alignment and impact (25%) | Targets where heat, missing shade and waiting people overlap; names who pays; fits heat action planning | Evidence list; priority map |
| Innovation and creativity (25%) | AI designs a costed cooling plan and knows when trees backfire; one network for repair and protection | Rejected tree row in the demo; two modes on one map |
| User experience (10%) | One screen, mode switch, shadows over time, arrows and text as well as color | Video and live app |

### Submission checklist

- [ ] Working prototype deployed on Cloud Run or Firebase, opening without a login
- [ ] Public GitHub repository, created during the hackathon, with no keys in the code
- [ ] Demo video under 3 minutes, as a public YouTube, Vimeo or Drive link
- [ ] Deck exported as a PDF covering problem, solution, feasibility and scalability
- [ ] Theme stated as Sustainability & Social Impact
- [ ] All materials in English
- [ ] One solution under one theme; every member a working professional, 21 or older, based in JAPAC
- [ ] Team of 2 to 4 confirmed as registered
- [ ] Gemini model name checked against the current Vertex AI model list before coding
- [x] 2 or 3 public sources added to the problem section

## Sources

Competition rules, timeline, themes, judging criteria and submission requirements were read from the official pages on Oct 12, 2026.

- [AI Builder Cup 2026: overview and timeline](https://aibuildercup.com)
- [Challenges and requirements](https://aibuildercup.com/themes.html)
- [Rewards and prizes](https://aibuildercup.com/rewards.html)
- [FAQs](https://aibuildercup.com/Faqs.html)

Precedents to verify before citing in the deck: Ahmedabad Heat Action Plan and its cool-roof pilots; Telangana Cool Roof Policy (2023); Paris OASIS schoolyards; American Forests Tree Equity Score.
