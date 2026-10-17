"""The offline rule proposer: deterministic, within the rules, and never scoring anything itself."""

from collections.abc import Callable
from typing import Any

import pytest

import ecozone_engine as e
from ecozone_agents.offline import RuleProposer
from ecozone_agents.ports import DesignProposal, ProposalRequest, RepairProposal
from ecozone_contract.runs import CandidateEvent, ProtectSearchRequest, RepairSearchRequest

pytestmark = pytest.mark.anyio


async def test_full_repair_search_with_the_rule_proposer(
    make_runner: Callable[..., Any], area: e.AreaModel, repair_request: RepairSearchRequest, emit: Any
) -> None:
    await make_runner(RuleProposer()).search(area, repair_request, emit)
    assert emit.types()[0] == "baseline" and emit.types()[-1] == "done"
    candidates = [ev.candidate for ev in emit.of(CandidateEvent)]
    assert candidates and all(cand.source == "gemini" for cand in candidates)
    assert any(cand.valid for cand in candidates)
    # the rules never offer a ventilation-rejected site
    assert not any(ch.site_id == "s_tree_9" for cand in candidates for ch in cand.changes)
    assert emit.done.best.cost_inr <= 700_000
    assert emit.done.explanation.source == "template"


async def test_full_protect_search_with_the_rule_proposer(
    make_runner: Callable[..., Any], area: e.AreaModel, protect_request: ProtectSearchRequest, emit: Any
) -> None:
    await make_runner(RuleProposer()).search(area, protect_request, emit)
    result = emit.done
    a, b, c_ = result.options
    assert [o.key for o in result.options] == ["A", "B", "C"]
    assert b.candidate.score <= a.candidate.score  # the proposal itself is always a candidate for B
    assert c_.candidate.score <= b.candidate.score
    assert (b.candidate.floor_area_pct or 0) >= protect_request.keep_floor_area_pct
    assert (c_.candidate.floor_area_pct or 0) >= protect_request.min_floor_area_pct
    # the rules turn the long side to the wind (axis 90 on the fake engine's 270° wind) and that lowers the risk
    assert b.candidate.score < a.candidate.score


async def test_the_rule_proposer_is_deterministic() -> None:
    brief = {
        "budget_inr": 500_000.0,
        "quick_win_target_inr": 100_000.0,
        "sites": [
            {
                "id": "s_b",
                "kind": "shade",
                "name": "B",
                "quantity": 1,
                "cost_inr": 100_000.0,
                "acs_gain": 2.0,
                "time_to_benefit": "weeks",
                "quick_win": True,
            },
            {
                "id": "s_a",
                "kind": "tree_row",
                "name": "A",
                "quantity": 1,
                "cost_inr": 100_000.0,
                "acs_gain": 2.0,
                "time_to_benefit": "years",
                "quick_win": False,
            },
        ],
    }
    request = ProposalRequest("repair", 1, 4, brief)
    first = await RuleProposer().propose(request)
    assert first == await RuleProposer().propose(request)
    assert len(first) == 4 and all(isinstance(p, RepairProposal) for p in first)
    # ties on gain per rupee are broken by site id
    head = first[0]
    assert isinstance(head, RepairProposal)
    assert head.changes[0][0] == "s_b" or head.changes[1][0] == "s_b"


async def test_protect_rules_respect_the_limits() -> None:
    brief = {
        "limits": {"max_floors": 8, "max_footprint_pct": 60, "min_green_pct": 10, "orientation_step_deg": 15},
        "wind_axis_deg": 90,
        "proposal": {"floors": 8, "footprint_pct": 60, "green_pct": 10, "orientation_deg": 0},
    }
    for round_no in (1, 2):
        for p in await RuleProposer().propose(ProposalRequest("protect", round_no, 4, brief)):
            assert isinstance(p, DesignProposal)
            assert 1 <= p.floors <= 8 and p.footprint_pct <= 60 and p.green_pct >= 10
            assert p.footprint_pct + p.green_pct <= 100 and p.orientation_deg % 15 == 0
