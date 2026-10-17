"""Determinism (ENGINEERING_RULES.md §9): the same inputs give byte-identical results, also through the search loop."""

import ecozone_engine as e
from evalkit.bench import Bench, building_change, canon
from evalkit.cases import AreaCases
from evalkit.results import Recorder

RUNS = 10


def _typical(bench: Bench, cases: AreaCases) -> list[e.Change]:
    return [bench.change(sid) for sid in cases.typical_portfolio]


def test_rescore_ten_runs_byte_equal(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    changes = _typical(bench, cases)
    outs = {canon(e.rescore(bench.area, changes, bench.costs)) for _ in range(RUNS)}
    rec.measure("determinism.rescore", "typical_portfolio", {"runs": RUNS, "distinct_results": len(outs)})
    assert len(outs) == 1


def test_rescore_ignores_change_order(bench: Bench, cases: AreaCases) -> None:
    changes = _typical(bench, cases)
    assert canon(e.rescore(bench.area, changes, bench.costs)) == canon(
        e.rescore(bench.area, changes[::-1], bench.costs)
    )


def test_building_rescore_byte_equal(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    case = cases.protect[0]
    change = building_change(case.parcel_id, case.proposal)
    outs = {canon(e.rescore(bench.area, [change], bench.costs)) for _ in range(RUNS)}
    rec.measure("determinism.rescore", "building", {"runs": RUNS, "distinct_results": len(outs)})
    assert len(outs) == 1


def test_hotspots_single_site_and_shadows_repeat(bench: Bench, cases: AreaCases) -> None:
    sid = cases.typical_portfolio[0]
    first = ([canon(h) for h in e.hotspots(bench.area, 10)], canon(e.single_site(bench.area, sid, bench.costs)))
    second = ([canon(h) for h in e.hotspots(bench.area, 10)], canon(e.single_site(bench.area, sid, bench.costs)))
    assert first == second
    changes = _typical(bench, cases)
    for time in ("13:00", "15:00", "16:00"):
        a = [p.wkb_hex for p in e.shadows(bench.area, time, changes)]  # pyright: ignore[reportArgumentType]
        b = [p.wkb_hex for p in e.shadows(bench.area, time, changes)]  # pyright: ignore[reportArgumentType]
        assert a == b


def test_greedy_repeats(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    bench.ensure_precomputed()
    case_id = cases.determinism_case
    assert bench.greedy_repeat is not None
    first, second = canon(bench.greedy[case_id].portfolio), canon(bench.greedy_repeat.portfolio)
    rec.measure("determinism.greedy", case_id, {"runs": 2, "identical": first == second})
    assert first == second


def test_repair_search_loop_repeats_with_fake_llm(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    case = cases.repair_case(cases.determinism_case)
    a, b = bench.repair_search(case, 1), bench.repair_search(case, 2)
    same_events = a.events == b.events
    rec.measure(
        "determinism.search",
        f"repair:{case.id}",
        {"runs": 2, "events": len(a.events), "identical_event_stream": same_events},
        "fake LLM (offline rule proposer); rescore is uncached, greedy and single-site results come from the engine",
    )
    assert same_events
    assert a.result.model_dump_json() == b.result.model_dump_json()


def test_protect_search_loop_repeats_with_fake_llm(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    case = cases.protect_case(cases.protect_search_case)
    a, b = bench.protect_search(case, 1), bench.protect_search(case, 2)
    rec.measure(
        "determinism.search",
        f"protect:{case.id}",
        {"runs": 2, "events": len(a.events), "identical_event_stream": a.events == b.events},
        "fake LLM (offline rule proposer)",
    )
    assert a.events == b.events
