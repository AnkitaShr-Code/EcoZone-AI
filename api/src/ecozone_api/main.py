"""App factory: API routes under /api, the built React app at / (api/RULES.md)."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routes import health
from .settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="EcoZone AI", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.include_router(health.router, prefix="/api")
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
