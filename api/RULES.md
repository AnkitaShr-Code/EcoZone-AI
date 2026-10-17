# api/ rules

Package `ecozone_api`. The FastAPI service: instant engine routes, agent-run routes, persistence, static serving of the app. Everything in [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md) applies; this file adds what is specific here.

## Layout

```
api/src/ecozone_api/
  main.py            app factory, lifespan (load bundles once), gzip, static files + SPA fallback
  settings.py        pydantic-settings: bundle root, unit costs file, store, app dist
  deps.py            Services (engine port, areas, unit-cost defaults, runs, per-bundle cache), area dependency
  errors.py          ApiError and the handlers that turn every failure into a contract ErrorBody
  routes/areas.py    area, layers, shadows, hotspots, sites
  routes/rescore.py  rescore (Repair, Protect preview, build-out) and greedy
  routes/runs.py     start, stream, stop agent runs; explain
  routes/plans.py    briefs (later; the app prints briefs itself for now)
  run_manager.py     runs as asyncio tasks, event log with seq, SSE replay, SearchRunner protocol
  to_contract.py     engine results → contract models (the only place rounding and CRS conversion happen)
  store/base.py      Store protocol
  store/memory.py    in-memory store (local, tests)
  store/firestore.py Firestore store (prod, WP9)
  runlog.py          BigQuery `runs` writer (best effort, WP9)
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

## Notes from WP6

- **Bundles.** `ECOZONE_BUNDLE_URI` is one area bundle (a directory holding `meta.json`) or a directory with one subdirectory per area. It is a local path or `gs://bucket/prefix`; a `gs://` location is downloaded to a temporary directory at startup, and a failed or empty download stops startup so a bad revision never takes traffic. While the engine is a stub, bundles fail to load with a warning and the service still starts.
- **Errors.** Engine `EngineInputError`s map to `SITE_NOT_FOUND`, `PARCEL_NOT_FOUND`, `QUANTITY_OUT_OF_RANGE` and `INVALID_CHANGE`; engine stubs to 501 `NOT_IMPLEMENTED`; malformed requests to 422 `INVALID_REQUEST`; anything else to 500 `INTERNAL`, logged.
- **Unit costs.** Defaults come from `pipeline/config/unit_costs.yaml` (`ECOZONE_UNIT_COSTS`; the image copies it), with `source` and `sourceUrl` kept.
- **Agents.** Runs and explain go through the `SearchRunner` protocol in `run_manager.py`. Since WP7, `create_app` builds the `ecozone_agents` runner by default (`build_runner`): `ECOZONE_LLM=fake` gives the offline proposer, `gemini` needs `GOOGLE_CLOUD_PROJECT`, `ECOZONE_GEMINI_LOCATION` and both model ids. Without them `UnavailableRunner` stays: a run ends with one `error` event (`NOT_IMPLEMENTED`) and explain returns 501. Tests pass `agent_settings=` to `create_app` to pin this. A runner sets `seq=0`; the manager numbers events. On stop, the runner should emit `done` with its best result before it exits (the task is cancelled).
- **Tests** run every route against `tests/conftest.py`'s fake engine and scripted runner, so they pass before WP5 and WP7.
- **Snapshot** writes the read routes only. The mock rescore keeps reading `_mock-engine.json`, so after a snapshot from a real bundle, mock-mode rescore needs that file regenerated (or use `make app-http`).
