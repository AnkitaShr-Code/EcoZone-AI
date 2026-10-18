"""App factory: API routes under /api, the built React app at / (api/RULES.md)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import ecozone_engine
from ecozone_agents import AgentSettings, build_runner

from . import errors
from .bundle_source import resolve_bundle_root
from .deps import EnginePort, Services, load_areas, load_unit_costs
from .routes import areas, health, rescore, runs
from .run_manager import RunManager, SearchRunner, UnavailableRunner
from .settings import Settings
from .store import FirestoreStore, MemoryStore, Store

log = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    engine: EnginePort | None = None,
    runner: SearchRunner | None = None,
    store: Store | None = None,
    agent_settings: AgentSettings | None = None,
) -> FastAPI:
    """`engine`, `runner` and `store` default to the real engine, the agents runner and the memory store.

    The default runner comes from the agent settings: `ECOZONE_LLM=fake` runs the offline proposer, and
    Gemini needs its Vertex settings. With neither, `UnavailableRunner` answers runs with NOT_IMPLEMENTED.
    """
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        port: EnginePort = engine or ecozone_engine  # pyright: ignore[reportAssignmentType]
        bundle_root = resolve_bundle_root(settings.bundle_uri)
        unit_cost_defaults = load_unit_costs(settings.unit_costs)
        search_runner = runner or build_runner(port, unit_cost_defaults, agent_settings) or UnavailableRunner()
        if store is not None:
            active_store = store
        elif settings.store == "firestore":
            try:
                active_store = FirestoreStore()
            except Exception:
                log.warning("firestore unavailable, falling back to memory store", exc_info=True)
                active_store = MemoryStore()
        else:
            active_store = MemoryStore()
        ai_status = "unavailable" if isinstance(search_runner, UnavailableRunner) else "active"
        log.info(
            "startup ECOZONE_LLM=%s store=%s ai_search=%s",
            (agent_settings or AgentSettings()).llm,
            type(active_store).__name__,
            ai_status,
        )
        app.state.services = Services(
            engine=port,
            areas=load_areas(port, bundle_root),
            unit_cost_defaults=unit_cost_defaults,
            runs=RunManager(search_runner, active_store),
        )
        yield

    app = FastAPI(
        title="EcoZone AI",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    errors.install(app)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    for router in (health.router, areas.router, rescore.router, runs.router):
        app.include_router(router, prefix="/api")
    _serve_app(app, settings.app_dist)
    return app


def _serve_app(app: FastAPI, dist: Path) -> None:
    """Serve app/dist; unknown non-/api paths fall back to index.html so in-app routes work."""
    index = dist / "index.html"
    if not index.is_file():
        return
    root = dist.resolve()
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:  # pyright: ignore[reportUnusedFunction]
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
