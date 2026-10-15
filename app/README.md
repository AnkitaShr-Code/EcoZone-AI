# app/

React + TypeScript front end (Vite). Lane: **U**.

**Read [UI_RULES.md](UI_RULES.md) before changing anything here.** It fixes the layout regions, the step pattern, the layer registry, tokens, copy and code structure so the UI doesn't drift.

## Run

```bash
npm install
npm run dev          # http://localhost:5173
```

| Script | Does |
| --- | --- |
| `npm run dev` | Dev server |
| `npm run typecheck` | TypeScript, strict |
| `npm run lint` | oxlint |
| `npm run build` | Typecheck and production build |
| `npm run mock:build` | Rebuild `public/mock/<area>/` from `scripts/source/*.osm.geojson` |

## Stack

React 19, Vite, Tailwind 4, shadcn/ui (Radix, Nova preset), lucide-react, MapLibre GL with the OpenFreeMap Positron basemap, deck.gl 9 (`MapboxOverlay`), Zustand for UI state, TanStack Query for server data.

## Data

`VITE_API_MODE=mock` (the default) serves `public/mock/deccan/`, built by `scripts/build-mock-data.mjs` from real OpenStreetMap geometry of the Deccan Gymkhana – Fergusson College area (fetched with `pipeline/fetch_sample.py`). Geometry, building shadows and footpath shade are computed for real; index scores, unit costs and intervention effects are **mock values** in the shapes of `src/api/types.ts`. The real backend replaces the adapter, not the components.

Design context: [../docs/DESIGN.md](../docs/DESIGN.md#c5-front-end-react--typescript).
