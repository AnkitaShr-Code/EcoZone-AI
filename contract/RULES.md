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

The UI's hand-written `app/src/api/types.ts` is the starting point. These changes are proposed by the engine side and need the U lane's agreement before the contract PR merges:

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
