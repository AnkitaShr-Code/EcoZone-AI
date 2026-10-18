# EcoZone AI: demo video script and shot list

Target 2:45, hard cap under 3:00. English. Recorded from the live app
(<https://ecozone-451227459430.asia-south1.run.app/>, area Deccan Gymkhana - Fergusson College, Pune).

**Single source of truth:** `script.json` holds the segments, narration templates and overlays that
the pipeline uses. This file explains them for people. Narration below is the *template*: every
`{{placeholder}}` is filled by `tools/fill.mjs` from the recorded take's `values.json` (numbers read
from the app's DOM during that take) or from `evals/REPORT.md`. No score is written here in advance.
`narration.md` and `narration-segments.json` hold the filled text for the current take.

## Honesty rules the narration follows

- Every number spoken or shown is read from the take's screen or from `evals/REPORT.md`.
- Gemini vs greedy: the narration states the outcome of *this take* exactly as the app shows it
  (`repair.verdict` picks the sentence). The close cites REPORT.md: live Gemini 1 win, 3 losses over 4
  budgets, single runs, varies run to run. Never "Gemini beats greedy" in general.
- Heat check: "agrees only weakly ... on held-out blocks, and that is not significant". Never "validated".
- Risk label, never "approve"/"deny". No temperatures, wind speeds or energy units.
- Not claimed: ADK, Earth Engine layers in the scores, saved plans. No people's names.
- The data has no bus stops (waiting points are hospitals, clinics, schools, colleges), so the hook
  talks about hospitals and schools, which are what the screen shows.

## Timing model

Audio-driven: each segment lasts `lead (0.25 s) + narration + tail (0.45 s)`. The recording is fitted to
it: the harness marks where each segment's actions end (`actionsEnd`); the hold after that is trimmed or
extended (last frame held); if the actions are longer than the narration they are sped up. The two live
searches are time-lapsed with a visible "Sped up N×" badge that also states the real search time.

## Shot list

| id | ~s | On screen (exact actions, recorded by `record.mjs`) | Overlays | Narration template |
| --- | --- | --- | --- | --- |
| s01 | 13 | App loaded, Repair mode, shade at 3 pm, Priority layer off. Cursor glides onto a footpath on Apte Path next to Joshi and Prayag hospitals; mouse-wheel zoom keeps it under the cursor; the app's tooltip appears: "Apte Path · Footpath in sun at 3 pm". | Title card: EcoZone AI / Repair and protect a city's cooling network / Live app · Deccan Gymkhana, Pune · built from OpenStreetMap | Three in the afternoon, in Pune. Outside these hospitals and schools, people wait on footpaths in full sun. Cities have money for trees and shade, but no quick way to decide where it helps most. |
| s02 | 15 | Open Layers, switch Priority on (blocks colored by priority), close. Click 1 pm, 4 pm, 3 pm (footpaths switch sun/shade). Hover the area's baseline cards. Click hotspot 1 in the list: the map flies to it, its card shows its scores. | Label: REPAIR · Priority map · footpath shade at 1, 3 and 4 pm. Callout on the baseline cards. | EcoZone AI maps where heat, missing afternoon shade and waiting people overlap. Shade comes from building geometry at one, three and four pm. Across Deccan Gymkhana, footpath shade is just {{area.pss}} out of 100. |
| s03 | 9 | Use this area. Type 10 in Total budget (lakh). Slider "Helps this summer" 20% -> 30% with the keyboard. Cursor rests on Draft cooling plan. | Label: REPAIR · Budget ₹ {{budget.lakh}} lakh · at least {{budget.quickWinPct}}% helps this summer | A planner sets a budget of {{budget.lakh}} lakh rupees. At least {{budget.quickWinPct}} percent must help this summer, not only trees that take years. |
| s04 | 16 | Click Draft cooling plan. Live search: "Preparing", Round 1, Round 2, each Gemini plan appearing with its engine score next to the greedy baseline. Time-lapsed. | Badge "Sped up N× · the live search took {{search.seconds}} s". Diagram: Gemini proposes -> Engine scores -> plain-code judge -> repeat; greedy baseline beside. | Gemini proposes whole plans. Our engine, not the model, scores every one, for shade, heat, green and ventilation. [If the app shows no rejected option:] It keeps tree rows off deep, narrow lanes, where they would block the breeze. A greedy baseline always runs alongside. |
| s05 | 17 | Plan: hover the verdict line ("AI plan beat the simple baseline" or "The simple baseline won"), the score cards, the facts (cost, helps this summer, ventilation check, waiting points shaded). Scroll to the intervention list grouped by type; collapse the cool-roof group, open the tree rows, click one marked "Shades a waiting point" (the map flies there). | Label: REPAIR · {{repair.verdictText}}. Callout on the verdict. Animated counter Area cooling score {{repair.acsBefore}} -> {{repair.acsAfter}}. Callout on the facts. | (Gemini won) In this run, Gemini's plan beat the simple baseline, and the app says so. It lifts the area cooling score from {{repair.acsBefore}} to {{repair.acsAfter}} for {{repair.costLakh}} lakh rupees, passes the ventilation check, and shades {{repair.waitPointsShaded}} waiting points. The mix: {{mix}}. (Baseline won) In this run, the simple baseline scored higher, and the app says so. Its plan lifts ... The mix: {{mix}}. ("beat" becomes "edged out" when the winning AI plan shows the same rounded score as the baseline.) |
| s06 | 8 | **Only if the live app lists a rejected option** (currently it never does, see the Phase 1 report): scroll to "Rejected by the ventilation check", click the tree row; the map flies to it. | Callout "Rejected, with the reason" | Tree rows on deep, narrow lanes are rejected, with the reason shown: canopy there would block the breeze. |
| s07 | 10 | Layers: Priority off. Toggle Today, then With plan, at 3 pm. | Label: REPAIR · Footpath shade at 3 pm · Today vs With plan. Box on the toggle. Callout "With plan: in shade at 3 pm" placed automatically where the two stills show footpath turning from the app's sun colour to its shade colour (`tools/shadediff.mjs`). | Here is that street at 3 pm, today and with the plan. Once the new trees grow, this footpath by a waiting point is in shade. |
| s08 | 7 | Accept plan. Download brief (opens the print dialog in a real browser; the recording shows the print view the browser prints). Scroll the brief: outcome table, phases by season. | Label: REPAIR · Printable cooling plan · phased by season | Accept the plan, and it exports as a printable brief: the work phased by season, with field checks for every site. |
| s09 | 10 | Switch to Protect. Pick "Open plot on an unnamed lane, 3,988.1 m², street 8 m wide" from the parcel list (pc_004); the map flies to it; the card shows plot size, street width, neighbours. | Label: PROTECT · Vacant plot · {{parcel.areaText}} · street {{parcel.streetM}} m wide | Protect asks the next question: will a new building undo this? Here is a vacant plot of {{parcel.areaSpoken}} square metres, on an {{parcel.streetM}} metre street. |
| s10 | 13 | Use this parcel. Default proposal (12 floors, 60% footprint, 10% green). Height slider +3 floors with the keyboard; scores and risk label update live. Hover the risk label. | Label: PROTECT · Live preview · risk measured on the parcel's own block. Callout on the risk label. | A developer proposes {{proposal.floors}} floors on {{proposal.footprintPct}} percent of the plot. Scores update live. The risk label is {{proposal.riskWord}}: ventilation on the parcel's own block falls by {{proposal.vciDrop}} points. (If the worst change is not ventilation, the fill tool swaps in "the worst change ... is N points, on X".) |
| s11 | 19 | Find better designs. Live design search time-lapsed. Options A, B, C appear; hover each; pick B (map shows it). | Badge "Sped up N× · the live design search took {{protectSearch.seconds}} s". Label: PROTECT · Options A, B, C · scored by the engine. Callout on the options. | Gemini searches for better designs, and the engine scores each one. Option B keeps {{B.floorAreaPct}} percent of the floor area and cuts the worst change to {{B.worst}}. Option C keeps {{C.floorAreaPct}} percent, at {{C.worst}}. The app shows the risk. The planner decides. |
| s12 | 7 | Recorded (Use this design, Run build-out at 200 m) but **cut by default** (`include: false`): on the live app the build-out of option B *raises* the area cooling score (new buildings add footpath shade), so it muddles the "cumulative harm" message in 7 seconds. | | Build-out applies the same envelope to every vacant parcel nearby, to show the cumulative effect. |
| s13 | 27 | Closing card over a blurred last frame. Cards appear as the narration reaches them. | Evidence card (all from REPORT.md): Gemini never computes a score (output guard) · Gemini vs greedy live: 1 win, 3 losses over 4 budgets, single runs · 49 of 49 evals pass · Heat check: Spearman ρ +0.187 on 33 held-out blocks, p = 0.30, weak and not significant · URL | Every number here comes from one deterministic engine. Gemini proposes and explains, but never computes a score. We report what we measured: over four budgets, live Gemini beat the greedy baseline once and lost three times. Our heat index agrees only weakly with Landsat surface temperature on held-out blocks, and that is not significant. EcoZone AI: repair and protect a city's cooling network. |

## Visual identity

Dark navy `#0f1e3a` and warm amber `#e89828` over the app's white map screens; system sans-serif; labels
at 30 px, callout tags 24 px, title 76 px (all at 1920x1080). Overlays are sparse: one label per segment,
at most one callout at a time; the app is the star. All overlays are HTML/CSS in `graphics/`, rendered
frame by frame (`tools/gfx.mjs`) and composited with ffmpeg.
