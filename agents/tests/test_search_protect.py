"""Protect design search: allowed ranges, the floor-area rules, options A, B and C (docs/PLANNING.md)."""

from collections.abc import Callable
from typing import Any

import pytest

import ecozone_contract as c
import ecozone_engine as e
from ecozone_agents import to_contract as tc
from ecozone_agents.facts import protect_facts
from ecozone_agents.fake_llm import ScriptedProposer
from ecozone_agents.guard import check_explanation, check_text, grounding_from_facts
from ecozone_agents.ports import DesignProposal
from ecozone_contract.runs import BaselineEvent, CandidateEvent, ErrorEvent, ProtectSearchRequest, RoundEvent

pytestmark = pytest.mark.anyio

# Proposal A: 8 floors, 60% footprint, 10% green, turned 0°. Floor area 480. Worst change 8 + 4.5 + 5 = 17.5.
# The fake engine: worst = floors × footprint / 60 + (100 − green) / 20 + |orientation − 90| / 18.


def design(
    label: str, floors: float = 8, footprint: float = 60, green: float = 10, orientation: float = 0
) -> DesignProposal:
    return DesignProposal(label, floors, footprint, green, orientation)


async def run(runner: Any, area: e.AreaModel, request: ProtectSearchRequest, emit: Any) -> Any:
    await runner.search(area, request, emit)
    return emit.done


async def test_options_a_b_c(
    make_runner: Callable[..., Any], area: e.AreaModel, protect_request: ProtectSearchRequest, emit: Any
) -> None:
    proposals = [
        design("Turned to the wind", orientation=90),  # 12.5, keeps 100%
        design("Six floors", floors=6),  # 15.5, keeps 75%: below B's 80%, above C's 50%
        design("Four floors, more green", floors=4, green=30, orientation=90),  # 4 + 3.5 + 0 = 7.5, keeps 50%
        design("Two floors", floors=2, green=40, orientation=90),  # keeps 25%: below the minimum, dropped
        design("Seven floors, turned", floors=7, orientation=90),  # 7 + 4.5 = 11.5, keeps 87.5%
    ]
    runner = make_runner(ScriptedProposer([proposals]), proposals_per_round=5, max_rounds=1)
    result = await run(runner, area, protect_request, emit)

    baseline = emit.of(BaselineEvent)[0].candidate
    assert baseline.id == "proposal" and baseline.source == "proposal" and baseline.round == 0
    assert baseline.score == 17.5 and baseline.floor_area_pct == 100 and baseline.risk.label == "MODERATE"

    a, b, c_ = result.options
    assert [o.key for o in result.options] == ["A", "B", "C"]
    assert a.candidate.id == "proposal" and a.design.floors == 8
    # B: lowest worst change keeping >= 80% of A's floor area -> "Seven floors, turned" (11.5), not the 75% design
    assert b.candidate.label == "Seven floors, turned" and b.candidate.score == 11.5
    assert b.candidate.floor_area_pct == 87.5
    # C: lowest worst change keeping >= 50% -> "Four floors, more green" (7.5)
    assert c_.candidate.label == "Four floors, more green" and c_.candidate.score == 7.5
    assert c_.candidate.floor_area_pct == 50
    assert result.best.id == b.candidate.id
    assert result.gemini_beat_greedy is None and result.rejected == []

    dropped = {ev.candidate.label: ev.candidate for ev in emit.of(CandidateEvent)}["Two floors"]
    assert not dropped.valid and dropped.invalid_reason == "Keeps less than 50% of the floor area"
    # trade-off text is grounded in engine values and shows the index, the change and the label
    assert a.trade_off == "All the proposed floor area. Worst change: ventilation falls by 18 (moderate risk)."
    assert b.trade_off == "Keeps 88% of the floor area. Worst change: ventilation falls by 12 (moderate risk)."
    assert c_.trade_off.startswith("Keeps 50% of the floor area.")
    assert [o.title for o in result.options] == ["Developer maximised", "Balanced", "Climate optimised"]


async def test_candidates_outside_the_allowed_ranges_are_dropped_with_reasons(
    make_runner: Callable[..., Any], area: e.AreaModel, protect_request: ProtectSearchRequest, emit: Any
) -> None:
    proposals = [
        design("Taller", floors=9),
        design("Wider", footprint=70),
        design("Less green", green=5),
        design("Too much built", footprint=60, green=45),
        design("Odd angle", orientation=100),
        design("Out of range angle", orientation=190),
        design("No floors", floors=0),
    ]
    runner = make_runner(ScriptedProposer([proposals]), proposals_per_round=10, max_rounds=1)
    result = await run(runner, area, protect_request, emit)
    reasons = {ev.candidate.label: ev.candidate.invalid_reason for ev in emit.of(CandidateEvent)}
    assert reasons == {
        "Taller": "Taller than the proposal",
        "Wider": "Footprint is zero or larger than the proposal",
        "Less green": "Less green than the proposal",
        "Too much built": "Footprint and green add up to more than 100%",
        "Odd angle": "Orientation must be a 15° step from 0 up to 180",
        "Out of range angle": "Orientation must be a 15° step from 0 up to 180",
        "No floors": "Fewer than one floor",
    }
    # nothing valid was found: B and C are the proposal itself, never a dropped design
    a, b, c_ = result.options
    assert a.candidate.id == b.candidate.id == c_.candidate.id == "proposal"
    assert "No design at this share lowers the worst change." in b.trade_off


async def test_a_design_that_matches_the_proposal_is_not_scored_again(
    make_runner: Callable[..., Any], engine: Any, area: e.AreaModel, protect_request: ProtectSearchRequest, emit: Any
) -> None:
    runner = make_runner(ScriptedProposer([[design("Same as A")]]), max_rounds=1)
    await run(runner, area, protect_request, emit)
    assert emit.of(CandidateEvent) == []
    assert len(engine.rescored) == 1


async def test_b_and_c_ties_go_to_the_larger_floor_area(
    make_runner: Callable[..., Any], area: e.AreaModel, protect_request: ProtectSearchRequest, emit: Any
) -> None:
    # Same worst change (11.5 vs 11.5): 7 floors / 60% (87.5% of A) and 8 floors / 52.5% with a different angle.
    proposals = [
        design("Seven floors", floors=7, orientation=90),
        design("Narrower", footprint=52.5, orientation=90, green=20),
    ]
    runner = make_runner(ScriptedProposer([proposals]), max_rounds=1)
    result = await run(runner, area, protect_request, emit)
    cands = {ev.candidate.label: ev.candidate for ev in emit.of(CandidateEvent)}
    assert cands["Seven floors"].score == 11.5
    assert cands["Narrower"].score == 8 * 52.5 / 60 + 4 + 0
    assert result.options[1].candidate.score == min(c.score for c in cands.values())


async def test_judge_stops_when_neither_b_nor_c_improves(
    make_runner: Callable[..., Any], area: e.AreaModel, protect_request: ProtectSearchRequest, emit: Any
) -> None:
    better = design("Turned", orientation=90)
    runner = make_runner(ScriptedProposer([[better], [design("Barely different", orientation=90, green=11)]]))
    await run(runner, area, protect_request, emit)
    # round 2 gains 0.05 on the worst change, below the 2 point threshold: no round 3
    assert [ev.round for ev in emit.of(RoundEvent)] == [1, 2]


async def test_proposer_sees_the_rules_and_the_best_designs_so_far(
    make_runner: Callable[..., Any], area: e.AreaModel, protect_request: ProtectSearchRequest, emit: Any
) -> None:
    proposer = ScriptedProposer([[design("Turned", orientation=90)], []])
    await run(make_runner(proposer), area, protect_request, emit)
    first, second = proposer.requests[0].brief, proposer.requests[1].brief
    assert first["limits"] == {
        "max_floors": 8,
        "max_footprint_pct": 60,
        "min_green_pct": 10,
        "orientation_step_deg": 15,
    }
    assert first["keep_floor_area_pct"] == 80 and first["min_floor_area_pct"] == 50
    assert first["wind_axis_deg"] == 90
    assert first["best_for_option_b"]["worst_change"] == 17.5  # type: ignore[index]
    assert second["best_for_option_b"]["label"] == "Turned"  # type: ignore[index]


async def test_unknown_parcel_is_reported(
    make_runner: Callable[..., Any], area: e.AreaModel, protect_request: ProtectSearchRequest, emit: Any
) -> None:
    request = protect_request.model_copy(update={"parcel_id": "pc_404"})
    await make_runner(ScriptedProposer([[]])).search(area, request, emit)
    [error] = emit.events
    assert isinstance(error, ErrorEvent) and error.code == "PARCEL_NOT_FOUND"


async def test_the_explanation_and_trade_offs_are_grounded_in_engine_values(
    make_runner: Callable[..., Any],
    engine: Any,
    area: e.AreaModel,
    unit_costs: c.UnitCosts,
    protect_request: ProtectSearchRequest,
    emit: Any,
) -> None:
    proposals = [design("Turned", orientation=90), design("Four floors", floors=4, orientation=90)]
    result = await run(make_runner(ScriptedProposer([proposals])), area, protect_request, emit)
    text = "\n".join(result.explanation.paragraphs)
    assert result.explanation.source == "template"
    assert text.startswith("As proposed, the worst effect is on ventilation: it falls by 18 on the parcel's block")
    assert "A 8-floor building faces a 18 m street." in text
    assert "Option B keeps" in text and "Option C keeps" in text and "The planner decides" in text
    # trade-off strings and the template pass the same guard as model text
    base = engine.rescore(
        area, [tc.building_change("pc_1", protect_request.proposal)], tc.engine_unit_costs(unit_costs)
    )
    facts = protect_facts(
        proposal=protect_request.proposal,
        result=base,
        parcel=None,
        parcel_id="pc_1",
        options=result.options,
        keep_floor_area_pct=80,
        min_floor_area_pct=50,
    )
    grounding = grounding_from_facts(facts)
    for option in result.options:
        assert check_text(option.trade_off, grounding) == []
    assert check_explanation(result.explanation.paragraphs, result.explanation.drivers, grounding) == []
