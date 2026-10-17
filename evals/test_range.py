"""Range: every score is finite and inside its contract range (0-100), reported on the test split of blocks."""

import math

import ecozone_engine as e
from ecozone_engine.settings import SETTINGS
from evalkit.bench import KINDS, Bench, building_change
from evalkit.bundle import BundleInfo
from evalkit.cases import AreaCases
from evalkit.results import Recorder

INDICES = ("vci", "hei", "gcs", "pss")


def _bad(value: float, lo: float = 0.0, hi: float = 100.0) -> bool:
    return not math.isfinite(value) or value < lo or value > hi


def _scores_problems(label: str, s: e.Scores) -> list[str]:
    return [f"{label} {i}={getattr(s, i)!r}" for i in INDICES if _bad(getattr(s, i))]


def _area_problems(label: str, s: e.AreaScores) -> list[str]:
    return [f"{label} {i}={getattr(s, i)!r}" for i in (*INDICES, "acs") if _bad(getattr(s, i))]


def result_problems(label: str, r: e.AreaResultData) -> list[str]:
    """Every out-of-range or non-finite number in one rescore result, over all blocks."""
    out = _area_problems(f"{label} area before", r.before) + _area_problems(f"{label} area after", r.after)
    for b in r.blocks:
        out += _scores_problems(f"{label} {b.block_id} before", b.before)
        out += _scores_problems(f"{label} {b.block_id} after", b.after)
    for name, v in (
        ("cost", r.cost_inr),
        ("quick_win_cost", r.quick_win_cost_inr),
        ("worst_vci_drop", r.worst_vci_drop),
    ):
        if not math.isfinite(v) or v < 0:
            out.append(f"{label} {name}={v!r}")
    if r.risk is not None and (not math.isfinite(r.risk.change) or r.risk.change < 0 or r.risk.change > 100):
        out.append(f"{label} risk change={r.risk.change!r}")
    return out


def test_baseline_scores_in_range(bench: Bench, info: BundleInfo, rec: Recorder) -> None:
    baselines = dict(bench.area.block_baselines)
    problems = _area_problems("area baseline", bench.area.area_baseline)
    for bid, s in baselines.items():
        problems += _scores_problems(f"baseline {bid}", s)
    test_ids = set(info.test_ids)
    assert test_ids, "the bundle has no test-split blocks"
    test_scores = [baselines[b] for b in sorted(test_ids) if b in baselines]
    spans = {i: [min(getattr(s, i) for s in test_scores), max(getattr(s, i) for s in test_scores)] for i in INDICES}
    rec.measure("range.baseline", "test_split", {"blocks": len(test_scores), "min_max": spans})
    rec.measure("range.baseline", "area", vars(bench.area.area_baseline))
    assert not problems, problems[:10]


def test_hotspots_in_range(bench: Bench) -> None:
    spots = e.hotspots(bench.area, 10_000)
    # P = HEI x (1 - PSS/100) x E x V is a ranking number, not a 0-100 score (PLANNING.md "Repair priority"): its
    # ceiling is 100 x the largest E x V.
    ceiling = 100.0 * (1.0 + SETTINGS.e_b_max) * max(SETTINGS.v_b_dense, SETTINGS.v_b_other)
    problems = [f"{h.block_id} priority={h.priority!r}" for h in spots if _bad(h.priority, 0.0, ceiling)]
    for h in spots:
        problems += _scores_problems(f"hotspot {h.block_id}", h.scores)
    assert [h.rank for h in spots] == list(range(1, len(spots) + 1))
    assert not problems, problems[:10]


def test_rescore_results_in_range(bench: Bench, cases: AreaCases, info: BundleInfo, rec: Recorder) -> None:
    """Greedy portfolios, every direction site at both quantities, and the Protect designs, all blocks."""
    results: dict[str, e.AreaResultData] = {}
    for rc in cases.repair:
        results[f"greedy:{rc.id}"] = bench.greedy_for(rc).portfolio.result
    for kind in KINDS:
        for sid in cases.direction_sites.get(kind, ()):
            qmin, qmax = bench.site_quantities(sid)
            results[f"{kind}:{sid}:qmin"] = bench.rescore([bench.change(sid, qmin)])
            results[f"{kind}:{sid}:qmax"] = bench.rescore([bench.change(sid, qmax)])
    for pc in cases.protect:
        results[f"building:{pc.parcel_id}"] = bench.rescore([building_change(pc.parcel_id, pc.proposal)])
    for g in cases.guard_designs:
        results[f"guard:{g.parcel_id}"] = bench.rescore([building_change(g.parcel_id, g.design)])

    problems: list[str] = []
    for label, r in results.items():
        problems += result_problems(label, r)

    test_ids = set(info.test_ids)
    lo = {i: 100.0 for i in INDICES}
    hi = {i: 0.0 for i in INDICES}
    for r in results.values():
        for b in r.blocks:
            if b.block_id in test_ids:
                for i in INDICES:
                    v = getattr(b.after, i)
                    lo[i], hi[i] = min(lo[i], v), max(hi[i], v)
    rec.measure(
        "range.rescore",
        "test_split_after_scores",
        {"results_checked": len(results), "min": lo, "max": hi, "problems": len(problems)},
    )
    assert not problems, problems[:10]


def test_single_site_gains_are_finite(bench: Bench, rec: Recorder) -> None:
    bench.ensure_precomputed()
    singles = [s for s in bench.single_cache.values()]
    bad = [s.site_id for s in singles if not math.isfinite(s.acs_gain) or abs(s.acs_gain) > 100 or s.cost_inr < 0]
    gains = [s.acs_gain for s in singles]
    rec.measure(
        "range.single_site",
        "all_valid_sites",
        {"sites": len(singles), "min_gain": min(gains), "max_gain": max(gains)},
    )
    assert not bad, bad[:10]
