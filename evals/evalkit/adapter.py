"""The engine as the agents see it (`EnginePort`), built only from the engine's public API.

This branch's `summary` and `layer` are not implemented yet, and the evals must not depend on them, so the two reads
the search loop needs are answered here from the loaded `AreaModel` and the bundle's meta.json:

- `summary`: reference date, wind direction and baseline for the writer and the Protect brief.
- `layer("sites")` and `layer("parcels")`: ids, kinds, quantity (the site's minimum quantity, the same one the
  engine's own `single_site` scores) and time to benefit.

`rescore` is never cached, so determinism through the search loop exercises the real engine. `greedy_baseline` and
`single_site` can be served from results computed in parallel worker processes by the same engine functions
(`evalkit.pool`), which only saves wall time; the cache keys include every input. Sites the canopy rule rejected come
back from `single_site` with `ventilation_ok=False`, which is what the search loop's catalog expects.
"""

from collections.abc import Sequence
from typing import cast

from shapely.geometry import Polygon

import ecozone_engine as e

from .bundle import BundleInfo

CostsKey = tuple[tuple[str, float], ...]
RescoreKey = tuple[tuple[str, str, float, tuple[tuple[str, float], ...]], ...]


def costs_key(costs: e.UnitCosts) -> CostsKey:
    return tuple(sorted((str(k), v.inr) for k, v in costs.items()))


def change_key(changes: Sequence[e.Change]) -> RescoreKey:
    return tuple(sorted((ch.kind, ch.site_id, ch.quantity, ch.params) for ch in changes))


class EvalEngine:
    def __init__(
        self,
        info: BundleInfo,
        greedy_cache: dict[tuple[float, float, CostsKey], e.PortfolioData],
        single_cache: dict[tuple[str, CostsKey], e.SingleSiteData],
    ) -> None:
        self.info = info
        self._greedy = greedy_cache
        self._single = single_cache
        self.rescored: dict[RescoreKey, e.AreaResultData] = {}
        self.rescore_calls = 0

    # ---------- reads the engine does not provide on this branch ----------

    def summary(self, area: e.AreaModel) -> e.AreaSummaryData:
        m = self.info.meta
        bx = cast("list[float]", m["bbox_xy"])
        return e.AreaSummaryData(
            area_id=area.area_id,
            name=str(m.get("name", area.area_id)),
            city=str(m.get("city", "")),
            bundle_version=area.bundle_version,
            bbox_xy=(bx[0], bx[1], bx[2], bx[3]),
            reference_date=str(m.get("reference_date", "")),
            shade_times=("13:00", "15:00", "16:00"),
            baseline=area.area_baseline,
            wind_from_deg=area.wind_from_deg,
            metres_per_floor=float(m.get("metres_per_floor", 3.0)),
        )

    def layer(self, area: e.AreaModel, name: e.LayerName) -> list[e.Feature]:
        if name == "sites":
            return [
                e.Feature(
                    s.site_id,
                    s.geometry,
                    {
                        "kind": s.kind,
                        "name": f"{s.kind} {s.site_id}",
                        "quantity": s.quantity_min,
                        "time_to_benefit": s.time_to_benefit,
                        "wait_point_id": s.wait_point_id,
                        "h_w": s.H_W,
                    },
                )
                for s in area.sites
            ]
        if name == "parcels":
            return [
                e.Feature(
                    p.parcel_id,
                    cast(Polygon, p.geometry),
                    {
                        "block_id": p.block_id,
                        "name": f"Parcel {p.parcel_id}",
                        "area_m2": p.area_m2,
                        "road_name": None,
                        "road_width_m": p.road_width_m,
                        "street_bearing_deg": p.street_bearing_deg,
                        "neighbour_height_m": p.neighbour_height_m,
                    },
                )
                for p in area.parcels
            ]
        raise NotImplementedError(f"the eval adapter answers only the sites and parcels layers, not '{name}'")

    # ---------- the engine's public API ----------

    def single_site(self, area: e.AreaModel, site_id: str, unit_costs: e.UnitCosts) -> e.SingleSiteData:
        key = (site_id, costs_key(unit_costs))
        if key in self._single:
            return self._single[key]
        site = next((s for s in area.sites if s.site_id == site_id), None)
        if site is not None and site.rejected:
            return e.SingleSiteData(
                site_id,
                0.0,
                0.0,
                (),
                ventilation_ok=False,
                ventilation_reason=f"Refused by the site rule ({site.rule})",
            )
        out = e.single_site(area, site_id, unit_costs)
        self._single[key] = out
        return out

    def rescore(self, area: e.AreaModel, changes: Sequence[e.Change], unit_costs: e.UnitCosts) -> e.AreaResultData:
        self.rescore_calls += 1
        out = e.rescore(area, changes, unit_costs)
        self.rescored[change_key(changes)] = out
        return out

    def greedy_baseline(
        self, area: e.AreaModel, budget_inr: float, unit_costs: e.UnitCosts, quick_win_share_pct: float
    ) -> e.PortfolioData:
        key = (budget_inr, quick_win_share_pct, costs_key(unit_costs))
        if key not in self._greedy:
            self._greedy[key] = e.greedy_baseline(area, budget_inr, unit_costs, quick_win_share_pct)
        return self._greedy[key]
