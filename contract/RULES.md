# contract/ rules

Package `ecozone_contract`. The API's wire shapes, as Pydantic v2 models. Everything in [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md) applies; this file adds what is specific here.

## What lives here

```
contract/
  pyproject.toml
  openapi.json                 generated, committed
  src/ecozone_contract/
    common.py                  Mode, ShadeTime, InterventionType, IndexKey, DriverTag, ErrorCode, Provenance enums; base model config
    area.py                    AreaSummary, UnitCost(s), layer feature properties
    repair.py                  Hotspot, Site, Change, AreaResult, BlockResult, RejectedOption
    protect.py                 BuildingDesign, RiskInfo, DesignOption
    runs.py                    SearchRequest, Candidate, SearchResult, Explanation, SearchEvent union
    export.py                  `ecozone-contract export` → openapi.json
  tests/
```

## Rules

- Only `pydantic` is imported. No engine types, no FastAPI.
- One base class sets `frozen=True`, `extra="forbid"`, `alias_generator=to_camel`, `populate_by_name=True`, `serialize_by_alias=True`. Every model inherits it.
- Closed sets are `Literal`/`StrEnum`, never free strings: modes, times, intervention kinds, driver tags, risk labels, error codes, provenance kinds, height sources.
- Tagged unions use a `type` (events) or `kind` (changes) discriminator so TS gets proper narrowing.
- Each model has a docstring; field docs use `Field(description=…)`. These flow into `openapi.json` and the generated TS.
- No defaults that hide missing data. A value that may be absent is `Optional` and documented.
- `openapi.json` is regenerated and committed in the same PR as any model change. CI regenerates and diffs it.

## Changes from the UI baseline

The UI's hand-written `app/src/api/types.ts` was the starting point. **Agreed by the U lane (Abhishek, Oct 16) and implemented in WP2.** The engine side proposed:

| Today in `types.ts` | Change | Reason |
| --- | --- | --- |
| `ParcelProps.shade` (lookup keyed `<footprint>_<height>`) | Removed. Previews call `rescore` with one `building` change | One scoring path (principle 3) |
| `Site.effects` (single-site shade and index deltas, combined additively in the mock) | Replaced by `Site.singleSite: { acsGain, drivers, ventilation }` from the engine. Combined effects always come from `rescore` | Effects of several sites are not additive (overlapping shade, linked green) |
| `BuildingProps.heightSource: 'osm' \| 'open_buildings' \| 'default'` | `'osm_height' \| 'osm_levels' \| 'open_buildings' \| 'typology'`; UI shows `typology` with the Default label | Typology defaults replace the flat 9 m |
| `AreaSummary.dataGaps` | Adds counts per height source and a list of skipped optional steps (for example `earth_engine`) | The data-caveat line in briefs is generated from this |
| `UnitCost` | Adds `source` (citation) | Planner-input defaults need a cited source |
| `runSearch(areaId, request)` streaming directly | `POST /api/areas/{area}/runs` returns `{ runId }`; `GET /api/runs/{runId}/events` streams; `DELETE /api/runs/{runId}` stops | Native `EventSource`, reconnect with `Last-Event-ID`, stop works across instances with affinity |
| `SearchEvent` | Adds `{ type: 'guard', … }` and `{ type: 'error', … }`; every event has `seq` | The UI can show a template fallback honestly; reconnect resumes |
| `AreaSummary.mock` | Kept; true only when served by the mock adapter (snapshot) | Snapshot numbers are real but frozen |

Segments stay named `segments` on the wire, and each one is a 10 m chunk with `shaded: [bool, bool, bool]`.

Also changed in WP2, from the U side:

| Change | Reason |
| --- | --- |
| `Change` is a tagged union: `{ kind: <intervention>, siteId, quantity }` or `{ kind: 'building', siteId, design: BuildingDesign }` | Replaces the loose `quantity` + `params` for buildings; TS narrows on `kind` |
| `Site.unitCost` removed; `Site.drivers` and `Site.ventilation` move under `singleSite` | Costs come from planner unit costs; single-site results are one engine object |
| `UnitCosts` keys are the intervention types (`tree_row`, `pocket_green`, `cool_roof`), not camelCase | So `unitCosts[site.type]` works on both sides |
| Optional fields are always present, as `null` when absent | Matches what the API serializes; the generated TS marks them required and nullable |
| `ParcelProps.nearbyBlocks` and `AreaSummary.engine.vRefM3`/levels removed | Engine-internal; the app never needs them |

**Mock mode (decided Oct 16):** until WP6 serves real routes, the app's mock adapter keeps a client-side mock rescore, labelled mock. Its engine-only inputs (per-site effects, the parcel shade lookup, mock constants) live in `app/public/mock/<area>/_mock-engine.json`, which is not part of the contract and is skipped by fixture validation. After WP6, interactive work runs against a local API on the tiny fixture, and the mock becomes an engine snapshot.

**Tooling note:** `openapi-typescript` 7 supports TypeScript 5 only and the app uses TypeScript 6, so `npm run gen:api` runs it through `npx` pinned to `openapi-typescript@7.13.0` with `typescript@5.9.3` instead of a dev dependency.
