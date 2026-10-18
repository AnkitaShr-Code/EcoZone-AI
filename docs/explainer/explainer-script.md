EcoZone AI. An explainer.

Part one. The overview.

EcoZone AI is a planning tool for cities that are getting hotter. In one sentence: it helps a city repair and protect its cooling network.

There are two modes. Repair is the lead. A ward planner picks an area, sets a budget in rupees, and gets a plan of trees, shade structures, depaving, pocket green and cool roofs, placed where they cool the most people. Protect is the second mode. A planner tests a proposed building on a vacant plot, sees what it does to the breeze, heat, green and shade around it, and gets better designs to compare.

We are team NeuralNodes. We are building this for the Google Cloud AI Builder Cup, in the Sustainability and Social Impact theme. The prototype is due on the eighteenth of October. Our demo area is a real part of Pune: Deccan Gymkhana and Fergusson College.

Part two. What problem we are solving.

Indian cities are heating up street by street. Between the years two thousand and twenty twenty, India recorded somewhere between ten and twenty thousand heat deaths, depending on which agency counted. In Pune, built-up area grew from about forty five percent of the city to fifty five percent in just over a decade.

The people who pay for this are the people who cannot buy their way out of the heat. Street vendors. Auto drivers. Commuters waiting at bus stops. Children in school yards. Patients outside hospitals. They spend the hottest afternoon hours outdoors, often with no shade at all.

There are two gaps in how cities decide things today.

The first gap is repair. A ward office might have a few lakh rupees for greening. Where should it go? Which streets? Trees, or shade structures, or removing paving? And which choices would backfire? Today that is mostly guesswork.

The second gap is protection. A new building can follow every rule on height and setbacks, and still block the breeze for the streets behind it, and pave over the green that cooled them. Nobody checks that before approval, because a proper microclimate study is specialist work.

Part three. How we solve it.

We treat a neighbourhood as one cooling network with three layers. Air paths, like wide streets that line up with the wind, and the river. Green patches, and the links between them. And waiting points, the places where people actually stand outdoors: schools, hospitals, markets and bus stops.

Repair fixes the network where it is broken. Protect stops new buildings from breaking it again.

Let me walk through Repair, step by step.

Step one, choose the area. The map ranks every block by priority. Priority is high where three things overlap: the block holds heat, its footpaths have no afternoon shade, and people wait nearby. Dense, low-rise housing gets extra weight.

Step two, set the budget. The planner enters, for example, twenty five lakh rupees, and checks the cost of each type of work. Then one more setting: how much of the budget must help this summer. We call these quick wins. Shade structures, cool roofs and depaving help within weeks or a season. Trees give the most value per rupee, but take years to give real shade. Without this setting, every plan came out as only trees. With a twenty percent quick-win share, the plan mixes trees with shade at the places people wait.

Step three, review the plan. This is where the AI works. Gemini proposes several mixes of interventions. Our scoring engine scores every one of them. Gemini looks at the scores and proposes better mixes, for up to two rounds. At the same time, the engine builds a simple baseline plan by ranking every site on value per rupee. We always compare Gemini against that baseline, and if Gemini does not beat it, we show the baseline and say so. That keeps us honest.

The plan also shows what was rejected and why. For example: a row of trees on a deep, narrow street is rejected, because the canopy would block the breeze and trap heat at night. A shade structure is suggested instead. That rule, no dense trees on streets where the buildings are taller than the street is wide, is one simple rule a planner can check on site.

The map can switch between today and with the plan. Footpaths turn from orange, meaning in sun, to green, meaning in shade, at one, three or four in the afternoon on a reference April day.

Step four, export the brief. A printable cooling plan, phased by season: shade before the March to May heat, depaving in the dry season, planting with the monsoon in June and July. Each site gets a field checklist for the ward engineer, because satellite images cannot see footpath width or overhead wires.

Now Protect.

The planner picks a vacant plot, then sets height, footprint, green space and orientation with sliders. The scores update instantly. A risk label says low, moderate or high, based on the single worst change, for example, ventilation falls by sixteen points. Gemini can explain the impact in plain words. Then Gemini searches for better designs, and the planner gets three options. Option A, the proposal as entered. Option B, balanced, which keeps most of the floor area but lowers the harm. Option C, climate optimised, which keeps at least a minimum of development. The planner picks one. There is also a build-out check: put the same building on every vacant plot nearby, and see the effect on the whole area. Then a printable planning brief.

Some rules hold everywhere. The tool never approves, denies or orders work. It shows evidence and options, and the planner decides. Every number comes from the engine, not from the AI. We never show degrees, wind speeds or energy figures, because our scores are screening indicators from zero to a hundred, not measurements. And anything entered by the planner, estimated by AI, or filled by a default is always labelled.

The scores, in plain words. Ventilation: how freely air moves along the street. Heat exposure: how much the area stores heat, from paving, missing greenery, building mass and dark roofs. Green connectivity: how much green there is and whether it links up. Footpath shade: how much footpath is in shadow in the afternoon, computed from building heights and the position of the sun. Repair combines heat, shade and green into one area cooling score, weighted by where people wait, and tries to raise it within the budget.

Part four. The technical architecture.

There are two halves: an offline pipeline, and one live service.

The offline pipeline runs once per city. It pulls buildings, roads and waiting points from OpenStreetMap. Building heights from Google Open Buildings. Vegetation and land cover from Sentinel-2 and ESA WorldCover, through Google Earth Engine. Wind direction from Open-Meteo. It computes the sun's position, the building shadows, the footpath sections and the baseline scores, and loads everything into BigQuery and Cloud Storage. Landsat surface temperature is used only to check that our heat score ranks blocks the same way real measurements do. One finding already: in our area, only eleven of six hundred and twenty eight buildings have a height in OpenStreetMap. So Open Buildings heights are essential.

The live system is one Cloud Run service, with four parts.

The front end is React, with a MapLibre base map and deck dot G L layers on top. A left panel holds the steps. The map shows the layers, and every layer can be switched on or off.

The scoring engine is plain Python. It holds one area in memory and is the only place a number is ever computed. One routine, rescore, applies any set of changes, trees, shade, depaving, cool roofs or new buildings, and recomputes only what is affected, in milliseconds.

The API is FastAPI. Sliders and plan edits call the engine directly, so they never wait for the AI.

The agent layer calls Gemini on Vertex AI directly through google-genai. A code router picks between two search modes — Repair and Protect — and a writer role. Both searches run on the same propose-score-judge loop. Gemini proposes. Plain code scores each option with the engine. Plain code decides when to stop. An output guard checks every answer: any number that did not come from the engine, or any temperature unit, is rejected.

Run records are stored in memory; Firestore persistence is planned. There are no API keys in the code; the service uses a Google Cloud service account.

Two rules hold the whole design together. Sliders never wait for AI. And the engine is the only place a number is made.

Part five. Where we are today.

The front end is built and working end to end on mock data. The map uses real OpenStreetMap geometry for Deccan Gymkhana, with real building shadows and footpath shade. The scores, costs and effects are mock values in exactly the shape the real engine will return, so switching to the real backend is one setting. The rules for the interface are written down, so the three of us build the same way.

What comes next: the real pipeline and engine, the agent loop on Vertex AI, deployment on Cloud Run, the tests, the demo video and the deck.

To remember it in one line: EcoZone AI shows a city where people are hottest, designs a costed plan to cool those places, knows when trees would backfire, and checks that the next building will not undo the work.
