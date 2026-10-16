# One command per check, the same locally and in CI (ENGINEERING_RULES.md §10).
.PHONY: check py-check app-check sync

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
