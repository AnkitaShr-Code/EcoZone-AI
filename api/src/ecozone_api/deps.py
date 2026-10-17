"""Services shared by the routes, built once at startup (api/RULES.md, "The bundle loads once").

`EnginePort` is the engine's public API as a protocol: production passes the `ecozone_engine`
module itself, tests pass a small fake.
"""

import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Protocol

import yaml
from fastapi import Depends, Request
from shapely.geometry import Polygon

import ecozone_contract as c
import ecozone_engine as e

from . import to_contract
from .errors import ApiError
from .run_manager import RunManager

log = logging.getLogger(__name__)


class EnginePort(Protocol):
    def load_bundle(self, path: Path) -> e.AreaModel: ...
    def summary(self, area: e.AreaModel) -> e.AreaSummaryData: ...
    def layer(self, area: e.AreaModel, name: e.LayerName) -> list[e.Feature]: ...
    def hotspots(self, area: e.AreaModel, top: int) -> list[e.HotspotData]: ...
    def single_site(self, area: e.AreaModel, site_id: str, unit_costs: e.UnitCosts) -> e.SingleSiteData: ...
    def rescore(self, area: e.AreaModel, changes: Sequence[e.Change], unit_costs: e.UnitCosts) -> e.AreaResultData: ...
    def greedy_baseline(
        self, area: e.AreaModel, budget_inr: float, unit_costs: e.UnitCosts, quick_win_share_pct: float
    ) -> e.PortfolioData: ...
    def shadows(self, area: e.AreaModel, time: e.ShadeTime, changes: Sequence[e.Change] = ()) -> list[Polygon]: ...


@dataclass
class Services:
    engine: EnginePort
    areas: dict[str, e.AreaModel]
    unit_cost_defaults: c.UnitCosts
    runs: RunManager
    _cache: dict[tuple[str, str], Any] = field(default_factory=dict[tuple[str, str], Any])
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def cached[T](self, area_id: str, key: str, compute: Callable[[], T]) -> T:
        """Per-area cache for values that depend only on the immutable bundle (layers, sites)."""
        with self._lock:
            if (area_id, key) not in self._cache:
                self._cache[(area_id, key)] = compute()
            return self._cache[(area_id, key)]


def load_unit_costs(path: Path) -> c.UnitCosts:
    """Default unit costs from pipeline/config/unit_costs.yaml (WP8); `source` keeps the citation."""
    rows: dict[str, dict[str, Any]] = yaml.safe_load(path.read_text())
    return c.UnitCosts.model_validate(
        {
            kind: {"unit": row["unit"], "inr": row["inr"], "source": row["source"], "sourceUrl": row.get("url")}
            for kind, row in rows.items()
        }
    )


def load_areas(engine: EnginePort, bundle_root: Path | None) -> dict[str, e.AreaModel]:
    """Each subdirectory of the bundle root is one area bundle. Stubs or a missing root load nothing."""
    if bundle_root is None:
        log.warning("ECOZONE_BUNDLE_URI is not set; no areas loaded")
        return {}
    dirs = [d for d in sorted(bundle_root.iterdir()) if d.is_dir()] if bundle_root.is_dir() else []
    areas: dict[str, e.AreaModel] = {}
    for directory in dirs:
        try:
            area = engine.load_bundle(directory)
        except (e.NotImplementedYetError, e.InvalidBundleError, FileNotFoundError) as exc:
            log.warning("Bundle %s not loaded: %s", directory.name, exc)
            continue
        areas[area.area_id] = area
    return areas


def get_services(request: Request) -> Services:
    return request.app.state.services


ServicesDep = Annotated[Services, Depends(get_services)]


def get_area(area_id: str, services: ServicesDep) -> e.AreaModel:
    area = services.areas.get(area_id)
    if area is None:
        loaded = ", ".join(sorted(services.areas)) or "none"
        raise ApiError("AREA_NOT_FOUND", f"Area {area_id} is not loaded on this server (loaded: {loaded}).", 404)
    return area


AreaDep = Annotated[e.AreaModel, Depends(get_area)]


def sites(services: Services, area: e.AreaModel) -> list[c.Site]:
    """Every candidate site with its single-site result at the default unit costs, cached per bundle."""

    def compute() -> list[c.Site]:
        costs = to_contract.unit_costs(services.unit_cost_defaults)
        return [
            to_contract.site(f, services.engine.single_site(area, f.id, costs))
            for f in services.engine.layer(area, "sites")
        ]

    return services.cached(area.area_id, "sites", compute)
