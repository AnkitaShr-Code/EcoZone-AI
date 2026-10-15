# UI rules

The contract for everything in `app/`. Read it before adding a screen, a control, a map layer or a colour. If a change needs to break a rule, change the rule here first, in the same PR, with the reason.

Product context: [../docs/PLANNING.md](../docs/PLANNING.md). Front-end design: [../docs/DESIGN.md](../docs/DESIGN.md#c5-front-end-react--typescript).

## 1. Principles

1. **The user always knows the next action.** Each mode is a short list of numbered steps. Exactly one step is open. It has one primary button that says what happens next.
2. **The panel controls, the map shows.** Every action lives in the workflow panel. Clicking the map only *selects*; the selection appears in the panel with its actions. No action exists only on the map.
3. **Quiet by default.** The UI chrome is neutral (greys, one accent). Colour is reserved for data meaning (shade, priority, intervention type, status).
4. **The UI never computes a score.** Every number comes from an API response. The front end only formats values. (The mock adapter stands in for the server and is the one exception; see §8.)
5. **Instant controls stay instant.** Sliders, toggles and manual plan edits call instant routes. Only explanations and searches call the AI, and those always show progress and can be stopped.
6. **Provenance is always visible.** Planner input, AI-estimated values, default values and mock data each carry a label, using one component.
7. **Build once.** Steps, stats, deltas, provenance labels, layers and formatters each have a single component or function. Repair and Protect reuse them.

## 2. Screen layout

Desktop first (planners use laptops). Minimum supported width: 1024 px. Below 1024 px the panel stacks above the map.

```
┌──────────────────────────────────────────────────────────────┐
│ Top bar: EcoZone AI · [Repair | Protect] · Area ▾ · Mock · ? │  48 px
├──────────────────┬───────────────────────────────────────────┤
│ Workflow panel   │ Map                          [Layers ▾]   │
│ 380 px, scrolls  │                                           │
│                  │                                           │
│ Selection card   │                                           │
│ (when selected)  │                                           │
│                  │                                           │
│ 1 Step ✓ summary │ [Today|With plan] [Shade time]  [Legend]  │
│ 2 Step (open)    │                                           │
│   …              │                                           │
│   [Primary]      │                                           │
│ 3 Step (locked)  │                                           │
└──────────────────┴───────────────────────────────────────────┘
```

| Region | Holds | Never holds |
| --- | --- | --- |
| Top bar | Product name, mode switch, area selector, data-source badge, help | Step actions, results |
| Workflow panel | Selection card (when something is selected), the mode's steps | Map styling controls |
| Map | Basemap and data layers, hover tooltips, selection highlight | Buttons that change the plan |
| Layers control (top right of map) | Layer toggles, grouped | Anything else |
| Display controls (bottom left of map) | Today / With plan (or With proposal), shown once a scenario exists; the three shade times, shown only when a shade or shadow layer is visible | A free time slider, anything that changes the plan |
| Legend (bottom right of map, collapsible) | Entries for the visible layers only, generated from the layer registry | Hand-written entries |
| Toasts (bottom left) | Short confirmations and errors | Results that must be read later |

## 3. Workflow steps

Each mode is a list of steps rendered by one `StepCard` component.

| State | Shows | Can the user act? |
| --- | --- | --- |
| Done | Number with a check, title, one-line summary of the choice, **Edit** | Edit reopens it |
| Open | Number, title, one-sentence instruction, the controls, one primary button, at most one secondary (outline) button below it | Yes |
| Locked | Number, title, why it is locked ("Set a budget first") | No |

Rules:

- One open step at a time. The primary button advances to the next step.
- Primary button text is a verb phrase naming the outcome: "Draft cooling plan", "Preview impact", "Export brief". Never "Next", "Submit" or "OK".
- At most one primary button per open step. Other actions are secondary (outline) or ghost buttons.
- Editing an earlier step never silently deletes later results. If the later results still make sense, mark the step stale ("Budget changed. Draft the plan again."). If they can no longer apply (a different parcel, a changed proposal after a design search), clear them, relock the later steps with `resetSteps`, and say so in a toast.

**Repair steps**

| # | Step | Primary action | Result |
| --- | --- | --- | --- |
| 1 | Choose area | Use this area | Priority map shown |
| 2 | Set budget | Draft cooling plan | Budget, quick-win share and unit costs; starts the AI search |
| 3 | Review plan | Accept plan | Live search progress, then the plan table, rejected options and before/after |
| 4 | Export brief | Download brief | Printable cooling plan |

**Protect steps**

| # | Step | Primary action | Result |
| --- | --- | --- | --- |
| 1 | Choose parcel | Use this parcel | Parcel selected on the map |
| 2 | Describe proposal | Find better designs | Scores update live as sliders move (instant preview) |
| 3 | Compare designs | Use this design | Options A, B and C |
| 4 | Check build-out (optional) | Run build-out | Area-wide effect on one street |
| 5 | Export brief | Download brief | Printable planning brief |

## 4. Map rules

- **Basemap:** OpenFreeMap Positron (light grey, muted labels). The basemap's own building layer is hidden; ours replaces it. No Google Maps tiles (Maps Platform AI terms).
- **One registry.** Every data layer is defined once in `src/map/layerRegistry.ts`: id, label, description, group, default visibility per mode, legend entries and its render function. The layers control, the legend and the deck.gl layer list are all generated from it. Adding a layer means adding one entry; nothing else.
- **Groups**, in this order in the layers control:
  - *Analysis:* priority, footpath shade, shadows.
  - *Plan:* interventions, rejected options.
  - *Context:* buildings (3D), waiting points.
- **Defaults:** at most three data layers are visible at once by default. Each step may set its own default layers, but it never hides a layer the user turned on in that step.
- **Only engine values.** The time control offers exactly the engine's reference times (1 pm, 3 pm, 4 pm on 15 April). The UI never invents in-between states.
- **Interaction:**
  - Hover shows a tooltip: name plus one value.
  - Click selects a feature: it is outlined and the panel shows the Selection card.
  - Esc or clicking empty map clears the selection.
- **Ground layers** (shadows, footpaths, priority) draw without depth testing. 3D layers (buildings, tree crowns) draw with it.
- **New data arrays.** deck.gl only redraws when a layer receives a new data array. Never mutate a layer's data in place.

## 5. Visual tokens

All colours, radii and font sizes come from CSS variables in `src/styles/globals.css` (shadcn's tokens plus the data tokens below). No hex values or Tailwind palette colours (`bg-red-500`) in components. Map colours come from `src/lib/colors.ts`, which reads the same tokens.

| Token | Meaning |
| --- | --- |
| `--data-sun` / `--data-shade` | Footpath in sun / in shade |
| `--priority-high` / `--priority-medium` / `--priority-low` | Repair priority classes |
| `--iv-tree`, `--iv-shade`, `--iv-depave`, `--iv-green`, `--iv-roof` | The five intervention types |
| `--status-rejected` | Rejected option |
| `--prov-planner`, `--prov-ai`, `--prov-default`, `--prov-mock` | Provenance labels |

Typography: Geist (shipped with the shadcn Nova preset). Sizes: 12 px (captions, labels), 14 px (body, controls), 16 px (step titles), 18 px (panel headings). Two weights only: 400 and 600. Numbers use tabular figures.

Icons: `lucide-react` only, 16 px in controls, 20 px max. An icon never stands alone without a text label or an `aria-label`.

## 6. Copy rules

- Sentence case everywhere. No ALL CAPS, no Title Case.
- Buttons are verbs naming the outcome. Links name their destination.
- Scores are written "64 / 100". Changes are written with a sign and an arrow, and are colour-coded only after that: "↓ 7", "↑ 12".
- Money: "₹ 25 lakh", "₹ 3.2 lakh". Planner-entered costs always carry the planner-input label.
- **Never** show temperature (°C), wind speed (m/s) or energy (kWh) units. The indices are 0–100 screening scores.
- Never say the tool approves, denies or orders work. Use "recommended", "rejected by the ventilation check", "planner decides".
- Empty states tell the user what to do: "Select a footpath or a site on the map to see its details."
- Errors say what happened and what to do: "Couldn't load the area. Check your connection and try again."

## 7. Provenance labels

One component, `<Provenance kind=…/>`:

| Kind | Text | When |
| --- | --- | --- |
| `planner` | Planner input | Budgets, unit costs, proposal values, envelopes |
| `ai` | AI-estimated | Imagery observations and anything Gemini estimated (with its confidence) |
| `default` | Default | Values filled by a documented default (for example a 9 m building height) |
| `mock` | Mock data | Every value while the mock adapter is active (shown once in the top bar, and on exported briefs) |

## 8. Code structure

```
app/
  UI_RULES.md            this file
  scripts/               build-mock-data.mjs (offline, like pipeline/)
  public/mock/<area>/    generated mock responses, one file per API route
  src/
    main.tsx, App.tsx    providers and the fixed layout regions
    shell/               TopBar, WorkflowPanel, SelectionCard
    components/ui/       shadcn components (generated; style changes only through tokens)
    components/          shared app components: StepCard, Stat, Delta, ScoreChanges, Provenance, RiskBadge,
                         SearchProgress, ExplanationCard, BriefSheet, EmptyState
    features/repair/     Repair steps, plan table, brief, useRepairPlan
    features/protect/    Protect steps, sliders, options, build-out, brief, useProtectSearch
    map/                 MapView, layerRegistry, LayersControl, Legend, TimeControl, layers/ (one render function per layer)
    api/                 types.ts (mirrors the Pydantic schemas), client.ts (one interface), mock/, http/
    state/               Zustand stores for UI state only
    lib/                 format.ts, colors.ts, utils.ts
    styles/              globals.css (tokens)
```

Rules:

- **Data access.** Only `src/api/` talks to data. Components call hooks (TanStack Query) that call `api`. No `fetch` anywhere else, and no component imports from `api/mock` directly.
- **Swappable adapter.** `api/client.ts` defines the `EcoZoneApi` interface. `VITE_API_MODE=mock|http` picks the adapter. Switching to the real backend is a change to that one variable.
- **Mock adapter.** `api/mock` is the only front-end code allowed to calculate values, because it stands in for the engine. It returns exactly the shapes in `api/types.ts`, with realistic latency.
- **State.** Server data lives in TanStack Query. UI state (mode, open step, visible layers, selection, shade time) lives in Zustand. Never copy server data into Zustand, with one deliberate exception: the **working scenario** (`state/scenarioStore.ts`), the change set the planner is reviewing. It starts from a search result and the planner then edits it, so it is planner state. Its scores always come from the rescore query (`state/useScenario.ts`), never from the store.
- **Agent runs.** A search is one streamed query (`useSearchRun`, built on TanStack's `streamedQuery`) reduced into `SearchState`. Repair and Protect use the same hook, the same `SearchProgress` component and the same `runSearch` contract, mirroring the single `LoopAgent` on the backend. Keep the hook in the workflow component, not a step, so a running search survives step changes.
- **Formatting.** Every displayed number goes through `lib/format.ts` (`formatScore`, `formatDelta`, `formatInr`, `formatPercent`, `formatCount`). No `toFixed` in components.
- **Naming.** Components are `PascalCase.tsx`; hooks are `useThing.ts`; everything else is `camelCase.ts`. One component per file. Feature components live in their feature folder until a second feature needs them; then they move to `components/`.
- **Size.** If a component file passes about 200 lines, split it.
- **Types.** TypeScript strict mode; no `any`. API types are written once in `api/types.ts`.

**Pitfalls already hit (don't repeat them):**

- MapLibre's stylesheet sets `position: relative` on its container. Give the map container a positioned wrapper; never put `absolute` on the container itself.
- Map overlays (layers control, time control, legend) need `z-10`, or the deck.gl canvas draws over them.
- A scroll area that holds `sr-only` text must be `relative`, or the hidden labels escape and make the whole page scroll.
- `maplibre-gl` stays in `optimizeDeps.exclude` in `vite.config.ts`; pre-bundling breaks its worker URL.
- deck.gl layer ids equal registry ids, so clicks and tooltips map back to the registry.
- `components/ui/slider.tsx` is edited to pass `aria-label` to the thumb (the focusable element). Keep that when re-adding the component.

## 9. Accessibility

- Every control is reachable and usable from the keyboard, with a visible focus ring.
- AI-written text is always marked as such (`ExplanationCard`) and says when it is out of date with the current plan or proposal.
- Colour is never the only signal: priority classes, shade and deltas also use words or arrows.
- Everything on the map has a list equivalent in the panel (the plan table, the hotspot list).
- Search progress is announced through an `aria-live` region.
- Text contrast meets WCAG AA in the light theme. A dark theme is out of scope for now, but tokens make it possible later.

## 10. Definition of done for a UI change

- Follows the step pattern and the layout regions above.
- Uses tokens, `format.ts` and `<Provenance/>`; no new colours or formatters.
- Any new map layer is a registry entry with a legend.
- Works on the mock adapter with no console errors.
- `npm run typecheck` and `npm run lint` pass.
