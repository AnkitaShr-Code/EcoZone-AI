"""Run the slow engine calls in worker processes (each loads the bundle once).

Greedy is minutes per case on the real bundle and the engine has no parallelism of its own, so the evals compute
the Repair greedy portfolios and every site's single-site result across processes. The functions called are the
engine's own public ones, unchanged; results come back as the engine's frozen dataclasses.
"""

import os
import time
from concurrent.futures import Future, ProcessPoolExecutor
from pathlib import Path

import ecozone_engine as e

CostRows = dict[str, tuple[str, float, str]]
"""kind -> (unit, inr, source)"""

_AREA: e.AreaModel | None = None


def to_costs(rows: CostRows) -> e.UnitCosts:
    return {kind: e.UnitCost(unit=u, inr=inr, source=src) for kind, (u, inr, src) in rows.items()}  # pyright: ignore[reportReturnType]


def _init(path: str) -> None:
    global _AREA
    _AREA = e.load_bundle(Path(path))


def _area() -> e.AreaModel:
    assert _AREA is not None
    return _AREA


def run_greedy(budget_inr: float, share_pct: float, rows: CostRows) -> tuple[e.PortfolioData, float]:
    t0 = time.perf_counter()
    out = e.greedy_baseline(_area(), budget_inr, to_costs(rows), share_pct)
    return out, time.perf_counter() - t0


def run_singles(site_ids: list[str], rows: CostRows) -> list[e.SingleSiteData]:
    costs = to_costs(rows)
    return [e.single_site(_area(), sid, costs) for sid in site_ids]


def worker_count() -> int:
    env = os.environ.get("ECOZONE_EVAL_WORKERS")
    return max(1, int(env)) if env else max(1, min(6, (os.cpu_count() or 2) - 1))


def make_pool(path: Path, workers: int) -> ProcessPoolExecutor:
    return ProcessPoolExecutor(max_workers=workers, initializer=_init, initargs=(str(path),))


__all__ = ["CostRows", "Future", "make_pool", "run_greedy", "run_singles", "to_costs", "worker_count"]
