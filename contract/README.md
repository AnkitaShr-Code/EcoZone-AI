# contract/

Pydantic v2 models for every API request, response and SSE event. Lanes: **D** and **U** agree changes; **A** implements routes against them.

The single source of the API shape: `openapi.json` is generated from these models and committed, and the app's TypeScript types are generated from that (`npm run gen:api` in `app/`). Mock fixtures in `app/public/mock/` are validated against these models in CI.

Implemented in WP2: `uv run ecozone-contract export` writes `openapi.json`; `npm run gen:api` in `app/` writes `app/src/api/generated.ts`. **Rules:** [RULES.md](RULES.md), on top of [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md).
