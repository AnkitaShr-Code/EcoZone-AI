"""The engine as the agents see it (`EnginePort`): the engine's public API with two additions.

- `rescore` is never cached, so determinism through the search loop exercises the real engine.
- `greedy_baseline` and `single_site` are served from results the workbench computed once with the same engine
  functions, which only saves wall time; the cache keys include every input.

`summary` and `layer` are the engine's own.
"""

from collections.abc import Sequence

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

    # ---------- the engine's own reads ----------

    def summary(self, area: e.AreaModel) -> e.AreaSummaryData:
        return e.summary(area)

    def layer(self, area: e.AreaModel, name: e.LayerName) -> list[e.Feature]:
        return e.layer(area, name)

    # ---------- the engine's public API ----------

    def single_site(self, area: e.AreaModel, site_id: str, unit_costs: e.UnitCosts) -> e.SingleSiteData:
        key = (site_id, costs_key(unit_costs))
        if key in self._single:
            return self._single[key]
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
