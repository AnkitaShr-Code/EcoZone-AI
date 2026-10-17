"""Service configuration from environment variables (ENGINEERING_RULES.md §10)."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ECOZONE_", env_file=".env", extra="ignore")

    bundle_uri: str | None = None
    """Directory holding one subdirectory per area bundle. Local paths and gs://bucket/prefix are supported.
    A gs:// URI expects objects at <prefix>/<area>/v<N>/<table>.parquet and meta.json (pipeline layout).
    The highest version of each area is downloaded into a flat temp dir at startup."""
    unit_costs: Path = REPO_ROOT / "pipeline" / "config" / "unit_costs.yaml"
    """Default unit costs with citations (WP8). The Docker image sets this to its copy."""
    store: Literal["memory", "firestore"] = "memory"
    app_dist: Path = REPO_ROOT / "app" / "dist"
    """Built React app served at /. The Docker image sets this to its copy of app/dist."""
