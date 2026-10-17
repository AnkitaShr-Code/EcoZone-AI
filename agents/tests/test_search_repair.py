"""Repair search: loop control flow, scorer drops, judge, greedy-wins, cancellation, fail-soft."""

import asyncio
import contextlib
from collections.abc import Callable
from typing import Any

import pytest

import ecozone_contract as c
import ecozone_engine as e
from ecozone_agents.fake_llm import ScriptedModel, ScriptedProposer
from ecozone_agents.llm import LlmWriter, WriterAnswer
from ecozone_agents.ports import RepairProposal
from ecozone_contract.runs import (
    BaselineEvent,
    CandidateEvent,
    DoneEvent,
    ErrorEvent,
    GuardEvent,
    RepairSearchRequest,
    RoundEvent,
)

pytestmark = pytest.mark.anyio


def prop(label: str, *ids: str | tuple[str, float]) -> RepairProposal:
    return RepairProposal(label, tuple((i, None) if isinstance(i, str) else i for i in ids))


GOOD_PLAN = prop("Shade, trees and a depaved yard", "s_shade_2", "s_tree_1", "s_dep_1")  # 6.3 gain, ₹ 5.8 lakh
BETTER_PLAN = prop("Add pocket green", "s_shade_1", "s_tree_1", "s_pg_1", "s_roof_1")  # 7.2 gain? see below


async def run(runner: Any, area: e.AreaModel, request: Any, emit: Any) -> None:
    await runner.search(area, request, emit)


async def test_event_order_and_result(
    make_runner: Callable[..., Any], area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    proposer = ScriptedProposer([[GOOD_PLAN], [GOOD_PLAN, prop("Swap", "s_shade_2", "s_dep_1", "s_pg_1")]])
    runner = make_runner(proposer)
    await run(runner, area, repair_request, emit)

    types = emit.types()
    assert types[0] == "baseline" and types[-1] == "done"
    assert types.count("done") == 1
    assert types[1] == "round"
    assert [ev.round for ev in emit.of(RoundEvent)] == [1, 2]
    baseline = emit.of(BaselineEvent)[0].candidate
    assert baseline.id == "greedy" and baseline.round == 0 and baseline.source == "greedy"

    result = emit.done
    assert result.rounds == 2
    # greedy ignores overlap (two bus-stop shades + a tree row = 5.3 gain); round 2's swap reaches 6.6
    assert baseline.score == 45.3
    assert result.best.score == 46.6 and result.best.source == "gemini"
    assert result.gemini_beat_greedy is True
    assert result.options is None
    assert result.explanation.source == "template"  # no writer in this run
    assert [r.site_id for r in result.rejected] == ["s_tree_9"]
    assert result.rejected[0].driver == "CANOPY_OBSTRUCTION"
    assert "deep and narrow" in result.rejected[0].reason
    # every number comes from the engine: the displayed cost is the engine's cost, rounded
    assert result.best.cost_inr == 671_500
    c.SearchResult.model_validate(result.model_dump())


async def test_greedy_is_computed_first_and_candidates_are_scored_by_rescore(
    make_runner: Callable[..., Any], engine: Any, area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    runner = make_runner(ScriptedProposer([[GOOD_PLAN]]))
    await run(runner, area, repair_request, emit)
    assert engine.greedy_calls == 1
    # the greedy plan is rescored once inside greedy_baseline, then once per distinct candidate
    scored = [sorted(ch.site_id for ch in call) for call in engine.rescored]
    assert ["s_dep_1", "s_shade_2", "s_tree_1"] in scored


async def test_scorer_drops_invalid_candidates_with_reasons(
    make_runner: Callable[..., Any], area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    proposals = [
        prop("Unknown site", "s_nope"),
        prop("Over budget", "s_shade_1", "s_shade_2", "s_dep_1", "s_pg_1"),
        prop("No quick wins", "s_tree_1", "s_pg_1"),
        prop("Rejected site", "s_tree_9"),
        prop("Quantity out of range", ("s_shade_1", 5)),
        prop("Same site twice", "s_shade_1", "s_shade_1"),
        prop("Empty"),
    ]
    runner = make_runner(ScriptedProposer([proposals]), proposals_per_round=10, max_rounds=1)
    await run(runner, area, repair_request, emit)
    by_label = {ev.candidate.label: ev.candidate for ev in emit.of(CandidateEvent)}
    reasons = {label: cand.invalid_reason for label, cand in by_label.items()}
    assert reasons["Unknown site"] == "Site s_nope is not in this area"
    assert reasons["Over budget"] == "Over budget"
    assert reasons["No quick wins"] == "Below the quick-win share"
    assert "deep and narrow" in (reasons["Rejected site"] or "")
    assert "takes 10 to 120 units; 5 is outside that range" in (reasons["Quantity out of range"] or "")
    assert reasons["Same site twice"] == "Site s_shade_1 appears twice"
    assert reasons["Empty"] == "The portfolio has no sites"
    assert not any(cand.valid for cand in by_label.values())
    # an over-budget candidate still shows the engine's cost and score, so the planner can see why
    assert by_label["Over budget"].cost_inr > 700_000 and by_label["Over budget"].score > 40
    # dropped candidates never become the result
    assert emit.done.best.id == "greedy" and emit.done.gemini_beat_greedy is False


async def test_duplicates_are_scored_once(
    make_runner: Callable[..., Any], engine: Any, area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    runner = make_runner(
        ScriptedProposer([[GOOD_PLAN, GOOD_PLAN, prop("Reordered", "s_dep_1", "s_tree_1", "s_shade_2")]]), max_rounds=1
    )
    await run(runner, area, repair_request, emit)
    assert len(emit.of(CandidateEvent)) == 1


async def test_greedy_wins_when_no_model_plan_beats_it(
    make_runner: Callable[..., Any], area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    weak = prop("Only roofs", "s_roof_1")
    runner = make_runner(ScriptedProposer([[weak]]))
    await run(runner, area, repair_request, emit)
    result = emit.done
    assert result.gemini_beat_greedy is False
    assert result.best.id == "greedy" and result.best.source == "greedy"
    assert any(ev.candidate.valid for ev in emit.of(CandidateEvent))  # a valid but weaker plan existed
    assert "baseline" in "\n".join(result.explanation.paragraphs)


async def test_judge_stops_when_nothing_improves_but_not_before_round_two(
    make_runner: Callable[..., Any], area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    runner = make_runner(
        ScriptedProposer(
            [[GOOD_PLAN], [prop("Same sites, a little more depaving", "s_shade_2", "s_tree_1", ("s_dep_1", 301))]]
        )
    )
    await run(runner, area, repair_request, emit)
    # round 1 improves on greedy; round 2 adds nothing above the threshold, so no round 3
    assert [ev.round for ev in emit.of(RoundEvent)] == [1, 2]


async def test_judge_runs_all_rounds_while_improving(
    make_runner: Callable[..., Any], area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    rounds = [
        [prop("r1", "s_shade_2", "s_tree_1", "s_roof_1")],  # 5.5: barely above greedy, but round 1 never stops
        [prop("r2", "s_shade_2", "s_tree_1", "s_dep_1")],  # 6.3: +0.8, above the threshold
        [prop("r3", "s_shade_2", "s_dep_1", "s_pg_1")],  # 6.6
        [prop("r4 never asked for", "s_shade_2", "s_dep_1")],
    ]
    runner = make_runner(ScriptedProposer(rounds), proposals_per_round=1, max_rounds=3)
    await run(runner, area, repair_request, emit)
    assert [ev.round for ev in emit.of(RoundEvent)] == [1, 2, 3]  # the round limit
    assert emit.done.rounds == 3


async def test_proposer_sees_a_compact_brief_with_greedy_and_best_so_far(
    make_runner: Callable[..., Any], area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    proposer = ScriptedProposer([[GOOD_PLAN], [GOOD_PLAN]])
    await run(make_runner(proposer), area, repair_request, emit)
    first, second = proposer.requests[0], proposer.requests[1]
    assert first.mode == "repair" and first.round == 1 and first.count == 4
    ids = [s["id"] for s in first.brief["sites"]]  # type: ignore[index]
    assert "s_tree_9" not in ids  # ventilation-rejected sites are not offered
    assert first.brief["greedy"]["score"] == 45.3  # type: ignore[index]
    assert second.brief["best_so_far"]["label"] == GOOD_PLAN.label  # type: ignore[index]
    assert "geometry" not in str(first.brief)


async def test_proposer_failure_ends_with_best_so_far_and_an_error_event(
    make_runner: Callable[..., Any], area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    from ecozone_agents.errors import ModelError

    runner = make_runner(ScriptedProposer(error=ModelError("quota")))
    await run(runner, area, repair_request, emit)
    assert emit.types()[-2:] == ["error", "done"]
    assert emit.of(ErrorEvent)[0].code == "INTERNAL"
    assert emit.done.best.id == "greedy"


async def test_proposer_timeout_is_fail_soft(
    make_runner: Callable[..., Any], area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    runner = make_runner(ScriptedProposer([[GOOD_PLAN]], delay_s=1.0), proposer_timeout_s=0.05)
    await run(runner, area, repair_request, emit)
    assert emit.types()[-2:] == ["error", "done"]


async def test_time_limit_returns_the_best_so_far(
    make_runner: Callable[..., Any], area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    runner = make_runner(ScriptedProposer([[GOOD_PLAN]]), search_time_limit_s=0.0)
    await run(runner, area, repair_request, emit)
    assert emit.types() == ["baseline", "done"]
    assert emit.done.rounds == 0


async def test_cancellation_emits_done_with_the_best_so_far(
    make_runner: Callable[..., Any], area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    runner = make_runner(ScriptedProposer([[GOOD_PLAN], [GOOD_PLAN]]))
    original = runner.proposer.propose

    async def slow_second_round(request: Any) -> Any:
        if request.round == 2:
            await asyncio.sleep(30)
        return await original(request)

    runner.proposer.propose = slow_second_round
    task = asyncio.create_task(runner.search(area, repair_request, emit))
    while "candidate" not in emit.types():
        await asyncio.sleep(0.01)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert emit.types()[-1] == "done"
    result = emit.done
    assert result.best.source == "gemini" and result.best.score == 46.3  # round 1's plan was kept
    assert result.rounds == 1
    assert result.explanation.source == "template"


async def test_cancellation_before_the_baseline_emits_nothing(
    make_runner: Callable[..., Any], engine: Any, area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    runner = make_runner(ScriptedProposer([[GOOD_PLAN]]))
    original = engine.greedy_baseline

    def slow(*args: Any) -> Any:
        import time

        time.sleep(0.3)
        return original(*args)

    engine.greedy_baseline = slow
    task = asyncio.create_task(runner.search(area, repair_request, emit))
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert emit.events == []


async def test_writer_guard_events_stream_during_the_search(
    make_runner: Callable[..., Any], area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    bad = WriterAnswer(paragraphs=["It is 3 °C cooler."], drivers=[])
    runner = make_runner(ScriptedProposer([[GOOD_PLAN]]), LlmWriter(ScriptedModel(writer=[bad])))
    await run(runner, area, repair_request, emit)
    guards = emit.of(GuardEvent)
    assert [g.fallback for g in guards] == [False, True]
    assert emit.types()[-3:] == ["guard", "guard", "done"]
    assert emit.done.explanation.source == "template"


async def test_grounded_writer_text_is_used(
    make_runner: Callable[..., Any], area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    good = WriterAnswer(
        paragraphs=[
            "The area cooling score goes from 40 to 46, with costs from the planner's unit costs (planner input)."
        ],
        drivers=["SHADE_GAIN"],
    )
    runner = make_runner(ScriptedProposer([[GOOD_PLAN]]), LlmWriter(ScriptedModel(writer=[good])))
    await run(runner, area, repair_request, emit)
    assert emit.done.explanation.source == "gemini"
    assert emit.of(GuardEvent) == []


async def test_engine_stub_is_reported_not_crashed(
    make_runner: Callable[..., Any], engine: Any, area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    engine.fail["greedy_baseline"] = e.NotImplementedYetError("greedy_baseline", "WP5b")
    await run(make_runner(ScriptedProposer([[GOOD_PLAN]])), area, repair_request, emit)
    [error] = emit.events
    assert isinstance(error, ErrorEvent) and error.code == "NOT_IMPLEMENTED"


async def test_unknown_budget_input_error_maps_to_its_code(
    make_runner: Callable[..., Any], engine: Any, area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    engine.fail["greedy_baseline"] = e.UnknownSiteError("s_x")
    await run(make_runner(ScriptedProposer([[GOOD_PLAN]])), area, repair_request, emit)
    assert emit.of(ErrorEvent)[0].code == "SITE_NOT_FOUND"
    assert not emit.of(DoneEvent)
