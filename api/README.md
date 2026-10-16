# api/

FastAPI service. Lane: **A**.

Instant REST routes (`/areas`, `/parcels`, `/interventions`, `/shadows`, `/buildout`, ...) call `engine/` directly with no AI in the path; agent-run routes (`/agent/runs`, `/agent/runs/{id}/events`) start and stream an `agents/` run over SSE. Also serves the built `app/` as static files, so the whole product is one Cloud Run container with no CORS and no proxy timeouts on long SSE streams.

Not yet implemented. Planned routes and schemas: [../docs/DESIGN.md](../docs/DESIGN.md#c3-api-service-fastapi).

**Rules:** [RULES.md](RULES.md) for this folder, on top of [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md).
