"""The one scoring path for every change set (docs/ENGINEERING_RULES.md principle 3)."""

from __future__ import annotations

from collections.abc import Sequence

from ._stub import NotImplementedYetError
from .model import AreaModel, AreaResultData, Change, UnitCosts


def rescore(area: AreaModel, changes: Sequence[Change], unit_costs: UnitCosts) -> AreaResultData:
    """Apply a change set and recompute only what it touches. Never mutates `area`."""
    raise NotImplementedYetError("rescore", "WP5b")
