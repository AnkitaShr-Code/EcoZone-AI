# One command per check, the same locally and in CI (ENGINEERING_RULES.md §10).
.PHONY: check py-check app-check sync api app-http

sync:
	uv sync --frozen

py-check:
	uv run ruff check
	uv run ruff format --check
	uv run pyright
	uv run lint-imports
	uv run pytest

app-check:
	cd app && npm run typecheck && npm run lint && npm run build

check: py-check app-check

# Local service: API at :8000 over ECOZONE_BUNDLE_URI (default data/bundles), and the app on it.
api:
	ECOZONE_BUNDLE_URI=$${ECOZONE_BUNDLE_URI:-data/bundles} uv run uvicorn ecozone_api.main:app --reload --port 8000

app-http:
	cd app && VITE_API_MODE=http npm run dev
