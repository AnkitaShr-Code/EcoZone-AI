"""Bundle loading: the only module that touches geopandas or pyarrow (engine/RULES.md)."""

from __future__ import annotations

from pathlib import Path

from ._stub import NotImplementedYetError
from .model import AreaModel


def load_bundle(path: Path) -> AreaModel:
    """Load one area bundle directory (GeoParquet tables + meta.json) into an immutable AreaModel."""
    raise NotImplementedYetError("load_bundle", "WP5a")
