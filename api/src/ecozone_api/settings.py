"""Service configuration from environment variables (ENGINEERING_RULES.md §10)."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ECOZONE_", env_file=".env", extra="ignore")

    bundle_uri: str | None = None
    """Area bundle directory, local path or gs:// URI. Unset until WP4 produces bundle v1."""
    store: Literal["memory", "firestore"] = "memory"
    app_dist: Path = REPO_ROOT / "app" / "dist"
    """Built React app served at /. The Docker image sets this to its copy of app/dist."""
