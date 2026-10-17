"""Speed (ENGINEERING_RULES.md §8): the targets measured on the bundle, p50 and p95 over repeated runs.

Simple timing with `time.perf_counter` (no extra dependency). Targets are the rules' own numbers; a miss fails the test
and stays in the report as a finding, never a relaxed threshold.
"""

import statistics
import time
from collections.abc import Callable

import ecozone_engine as e
from evalkit.bench import Bench, building_change
from evalkit.cases import AreaCases
from evalkit.results import Recorder

RUNS = 20


TARGET_START_MS = 10_000
TARGET_REPAIR_RESCORE_MS = 200
TARGET_PROTECT_RESCORE_MS = 100
TARGET_SHADOWS_MS = 500
TARGET_SEARCH_MS = 60_000


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    k = (len(ordered) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def time_ms(fn: Callable[[], object], runs: int = RUNS) -> dict[str, float]:
    fn()  # warm-up
    samples: list[float] = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return {
        "runs": runs,
        "p50_ms": round(statistics.median(samples), 1),
        "p95_ms": round(percentile(samples, 0.95), 1),
        "min_ms": round(min(samples), 1),
        "max_ms": round(max(samples), 1),
    }


def test_service_start_bundle_load(bench: Bench, rec: Recorder) -> None:
    ms = bench.load_seconds * 1000
    rec.measure("speed.load_bundle", "one_load", {"ms": round(ms), "target_ms": TARGET_START_MS})
    assert ms < TARGET_START_MS


def test_repair_rescore_latency(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    bench.ensure_precomputed()  # the slow setup finishes first
    changes = [bench.change(sid) for sid in cases.typical_portfolio]
    stats = time_ms(lambda: e.rescore(bench.area, changes, bench.costs))
    stats["sites"] = len(changes)
    stats["target_ms"] = TARGET_REPAIR_RESCORE_MS
    rec.measure("speed.rescore", "repair_portfolio", stats)
    assert stats["p95_ms"] <= TARGET_REPAIR_RESCORE_MS, stats


def test_empty_rescore_latency(bench: Bench, rec: Recorder) -> None:
    """The cost with nothing changed shows how much of a rescore is fixed overhead."""
    stats = time_ms(lambda: e.rescore(bench.area, [], bench.costs), runs=10)
    rec.measure("speed.rescore", "no_changes", stats)


def test_protect_rescore_latency(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    pc = cases.protect[0]
    change = building_change(pc.parcel_id, pc.proposal)
    stats = time_ms(lambda: e.rescore(bench.area, [change], bench.costs))
    stats["target_ms"] = TARGET_PROTECT_RESCORE_MS
    rec.measure("speed.rescore", "protect_building", stats)
    assert stats["p95_ms"] <= TARGET_PROTECT_RESCORE_MS, stats


def test_shadows_with_portfolio_latency(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    changes = [bench.change(sid) for sid in cases.typical_portfolio]
    stats = time_ms(lambda: e.shadows(bench.area, "15:00", changes), runs=10)
    stats["target_ms"] = TARGET_SHADOWS_MS
    rec.measure("speed.shadows", "one_time_with_portfolio", stats)
    assert stats["p95_ms"] <= TARGET_SHADOWS_MS, stats


GREEDY_RUNS = 5


def test_greedy_mid_budget_time(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    """Greedy at the mid budget, repeated; there is no target for it in the rules. Every Repair case is also timed
    once, in an otherwise idle process."""
    case = cases.repair_case(cases.speed_case)

    def run() -> object:
        return e.greedy_baseline(bench.area, case.budget_inr, bench.costs, case.quick_win_share_pct)

    samples: list[float] = []
    for _ in range(GREEDY_RUNS):
        t0 = time.perf_counter()
        run()
        samples.append(time.perf_counter() - t0)
    rec.measure(
        "speed.greedy",
        case.id,
        {
            "budget_inr": case.budget_inr,
            "runs": GREEDY_RUNS,
            "p50_ms": round(statistics.median(samples) * 1000),
            "p95_ms": round(percentile(samples, 0.95) * 1000),
            "min_ms": round(min(samples) * 1000),
            "max_ms": round(max(samples) * 1000),
        },
        "wall time of greedy_baseline, repeated, after the first (warm) run",
    )
    for rc in cases.repair:
        r = bench.greedy_for(rc)
        rec.measure("speed.greedy", f"first run:{rc.id}", {"seconds": round(r.seconds, 1)})


def test_search_three_rounds_time(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    """Whole search with the offline proposer, greedy and single-site results precomputed (so this is the loop and its
    rescores, not the baseline). Includes the loop's time limit behaviour only through its wall time."""
    rc = cases.repair_case(cases.speed_case)
    run = bench.repair_search(rc)
    ms = run.seconds * 1000
    rec.measure(
        "speed.search",
        rc.id,
        {
            "ms": round(ms),
            "rounds": run.result.rounds,
            "rescores": run.engine.rescore_calls,
            "target_ms": TARGET_SEARCH_MS,
        },
        "offline proposer; greedy baseline and single-site results precomputed in parallel, excluded from this time",
    )
    assert ms < TARGET_SEARCH_MS
