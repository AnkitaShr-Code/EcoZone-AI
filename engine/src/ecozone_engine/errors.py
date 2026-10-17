"""Errors the engine raises for bad input. The API maps each to a contract error code (api/RULES.md)."""

from __future__ import annotations


class EngineInputError(ValueError):
    """Base for input the engine refuses. Messages are shown to the planner, so they say what to do."""


class UnknownSiteError(EngineInputError):
    def __init__(self, site_id: str) -> None:
        self.site_id = site_id
        super().__init__(f"Site {site_id} is not in this area. Reload the site list and try again.")


class UnknownParcelError(EngineInputError):
    def __init__(self, parcel_id: str) -> None:
        self.parcel_id = parcel_id
        super().__init__(f"Parcel {parcel_id} is not in this area. Pick a parcel on the map.")


class QuantityOutOfRangeError(EngineInputError):
    def __init__(self, site_id: str, quantity: float, minimum: float, maximum: float) -> None:
        self.site_id = site_id
        super().__init__(f"Site {site_id} takes {minimum:g} to {maximum:g} units; {quantity:g} is outside that range.")


class InvalidChangeError(EngineInputError):
    """A change the engine refuses for a domain reason, for example a tree row on a street with H/W ≥ 1."""


class InvalidBundleError(ValueError):
    """Bundle directory is missing a required field or table (not an input error from the planner)."""

    def __init__(self, field: str, path: str) -> None:
        self.field = field
        super().__init__(f"Bundle at {path!r} is missing required field {field!r}.")
