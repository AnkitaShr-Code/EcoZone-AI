"""App factory: API routes under /api, the built React app at / (api/RULES.md)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import ecozone_engine

from . import errors
from .deps import EnginePort, Services, load_areas, load_unit_costs
from .routes import areas, health, rescore, runs
from .run_manager import RunManager, SearchRunner, UnavailableRunner
from .settings import Settings
from .store import MemoryStore, Store


def create_app(
    settings: Settings | None = None,
    *,
    engine: EnginePort | None = None,
    runner: SearchRunner | None = None,
    store: Store | None = None,
) -> FastAPI:
    """`engine`, `runner` and `store` default to the real engine, the agents runner and the memory store."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        port: EnginePort = engine or ecozone_engine  # pyright: ignore[reportAssignmentType]
        bundle_root = Path(settings.bundle_uri) if settings.bundle_uri else None
        app.state.services = Services(
            engine=port,
            areas=load_areas(port, bundle_root),
            unit_cost_defaults=load_unit_costs(settings.unit_costs),
            runs=RunManager(runner or UnavailableRunner(), store or MemoryStore()),
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
