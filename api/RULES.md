# api/ rules

Package `ecozone_api`. The FastAPI service: instant engine routes, agent-run routes, persistence, static serving of the app. Everything in [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md) applies; this file adds what is specific here.

## Layout

```
api/src/ecozone_api/
  main.py            app factory, lifespan (load bundle once), static files + SPA fallback
  settings.py        pydantic-settings: bundle URI, store, project, model ids
  deps.py            dependency providers: area, store, agent runner
  routes/areas.py    area, layers, hotspots, sites
  routes/rescore.py  rescore (Repair, Protect preview, build-out)
  routes/runs.py     start, stream, stop agent runs; explain
  routes/plans.py    briefs
  to_contract.py     engine results → contract models (the only place rounding and CRS conversion happen)
  store/base.py      Store protocol
  store/memory.py    in-memory store (local, tests)
  store/firestore.py Firestore store (prod)
  runlog.py          BigQuery `runs` writer (best effort)
  snapshot.py        `uv run ecozone snapshot --area deccan` → app/public/mock/<area>/
```

## Routes

All under `/api`. Request and response bodies are `contract` models; nothing returns a bare dict.

| Method and path | Contract | Notes |
| --- | --- | --- |
| `GET /areas/{area}` | `AreaSummary` | |
| `GET /areas/{area}/layers/{name}` | layer `FeatureCollection` | WGS84, gzip, `ETag` = bundle version; cacheable |
| `GET /areas/{area}/hotspots?top=` | `Hotspot[]` | |
| `GET /areas/{area}/sites?types=` | `Site[]` | single-site results computed at startup and cached per bundle |
| `POST /areas/{area}/rescore` | `RescoreRequest` → `AreaResult` | Repair edits, Protect previews (`building` changes) and build-out; engine only |
| `GET /areas/{area}/shadows?t=&changes=` | shadow `FeatureCollection` | baseline served from the bundle; with changes computed by the engine |
| `POST /areas/{area}/greedy` | `Candidate` | |
| `POST /areas/{area}/runs` | `SearchRequest` → `{ runId }` | starts the search agent run |
| `GET /runs/{runId}/events` | SSE of `SearchEvent` | `id:` = `seq`; supports `Last-Event-ID`; heartbeat every 15 s |
| `DELETE /runs/{runId}` | 204 | stops the run; best so far is kept |
| `POST /areas/{area}/explain` | `ExplainRequest` → `Explanation` | synchronous, 20 s timeout, template fallback on timeout |
| `GET /plans/{planId}/brief` | HTML | printable |
| `GET /healthz` | `{ ok, bundleVersion }` | |

## Rules

- **Instant routes are sync `def`** (FastAPI runs them in the threadpool) because the engine is CPU-bound; they never `await` Gemini, Firestore or BigQuery. Persistence and run logging after an instant route happen in a background task and never fail the response.
- **The bundle loads once** in the lifespan handler into an immutable `AreaModel` per area. Requests never mutate it.
- **Validation** is Pydantic plus engine checks (unknown site id, quantity outside the site's range, unknown parcel) mapped to contract error codes with 404 or 422.
- **Agent runs** execute as asyncio tasks inside the instance; events go to an in-memory per-run queue that keeps the full event log for `Last-Event-ID` replay. Cloud Run session affinity keeps the stream on the instance that owns the run. Finished runs and their best result are written to the store.
- **Static app**: `app/dist` is served at `/`; unknown non-`/api` paths return `index.html`.
- **Snapshot**: `snapshot.py` calls the same handlers as the routes (not the engine directly), so mock fixtures are exactly what the API returns.
