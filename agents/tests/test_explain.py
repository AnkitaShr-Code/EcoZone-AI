"""Writer → guard → retry → template, and the 20 s timeout fallback (agents/RULES.md "Output guard")."""

from collections.abc import Callable
from typing import Any

import pytest

import ecozone_contract as c
import ecozone_engine as e
from ecozone_agents import AgentSettings
from ecozone_agents.errors import ModelError
from ecozone_agents.explain import write_explanation
from ecozone_agents.fake_llm import ScriptedModel
from ecozone_agents.llm import LlmWriter, WriterAnswer
from ecozone_contract.runs import GuardEvent

FACTS: dict[str, object] = {
    "mode": "repair",
    "before": {"acs": 40.0, "pss": 30.0},
    "after": {"acs": 44.4, "pss": 35.6},
    "cost_inr": 925_000.0,
    "budget_inr": 1_000_000.0,
    "quick_win_cost_inr": 200_000.0,
    "wait_points_covered": 2,
    "counts_by_kind": {"shade": 2},
    "drivers": ["SHADE_GAIN"],
    "driver_labels": {"SHADE_GAIN": "adds footpath shade"},
}
GOOD = WriterAnswer(
    paragraphs=["The score goes from 40 to 44, at ₹ 9.3 lakh from the planner's unit costs (planner input)."],
    drivers=["SHADE_GAIN"],
)
BAD = WriterAnswer(paragraphs=["The score jumps by 9 and it is 3 °C cooler."], drivers=["SHADE_GAIN"])

pytestmark = pytest.mark.anyio


async def test_accepts_a_grounded_answer(settings: Callable[..., AgentSettings], emit: Any) -> None:
    model = ScriptedModel(writer=[GOOD])
    out = await write_explanation(LlmWriter(model), FACTS, settings(), emit)
    assert out.source == "gemini"
    assert out.paragraphs == GOOD.paragraphs
    assert out.drivers == ["SHADE_GAIN"]
    assert emit.events == []
    assert model.count("writer") == 1


async def test_rejects_once_then_accepts_the_retry(settings: Callable[..., AgentSettings], emit: Any) -> None:
    model = ScriptedModel(writer=[BAD, GOOD])
    out = await write_explanation(LlmWriter(model), FACTS, settings(), emit)
    assert out.source == "gemini"
    [guard] = emit.of(GuardEvent)
    assert guard.fallback is False
    assert any("°C" in v for v in guard.violations)
    # the retry is told what was wrong
    assert model.calls[1].json["rejected_previous_answer_because"] == guard.violations
    assert "rejected_previous_answer_because" not in model.calls[0].json


async def test_two_rejections_fall_back_to_the_template(settings: Callable[..., AgentSettings], emit: Any) -> None:
    model = ScriptedModel(writer=[BAD])
    out = await write_explanation(LlmWriter(model), FACTS, settings(), emit)
    assert out.source == "template"
    assert out.drivers == ["SHADE_GAIN"]
    assert model.count("writer") == 2  # one regeneration, no more
    assert [g.fallback for g in emit.of(GuardEvent)] == [False, True]
    assert "planner input" in "\n".join(out.paragraphs)


async def test_drivers_outside_the_engine_set_are_rejected(settings: Callable[..., AgentSettings], emit: Any) -> None:
    wrong = WriterAnswer(paragraphs=GOOD.paragraphs, drivers=["SHADE_GAIN", "ALBEDO_GAIN"])
    out = await write_explanation(LlmWriter(ScriptedModel(writer=[wrong])), FACTS, settings(), emit)
    assert out.source == "template"
    assert "ALBEDO_GAIN" in emit.of(GuardEvent)[0].violations[0]


async def test_empty_driver_list_uses_the_engine_drivers(settings: Callable[..., AgentSettings]) -> None:
    answer = WriterAnswer(paragraphs=GOOD.paragraphs, drivers=[])
    out = await write_explanation(LlmWriter(ScriptedModel(writer=[answer])), FACTS, settings())
    assert out.source == "gemini" and out.drivers == ["SHADE_GAIN"]


async def test_timeout_falls_back_to_the_template(settings: Callable[..., AgentSettings], emit: Any) -> None:
    model = ScriptedModel(writer=[GOOD], delay_s={"writer": 1.0})
    out = await write_explanation(LlmWriter(model), FACTS, settings(explain_timeout_s=0.05), emit)
    assert out.source == "template"
    assert emit.events == []  # a timeout is not a guard rejection


async def test_model_error_falls_back_to_the_template(settings: Callable[..., AgentSettings]) -> None:
    model = ScriptedModel(writer=[ModelError("quota")])
    out = await write_explanation(LlmWriter(model), FACTS, settings())
    assert out.source == "template"


async def test_no_writer_means_template(settings: Callable[..., AgentSettings]) -> None:
    out = await write_explanation(None, FACTS, settings())
    assert out.source == "template"


async def test_explain_route_times_out_to_template(
    make_runner: Callable[..., Any], area: e.AreaModel, unit_costs: c.UnitCosts
) -> None:
    model = ScriptedModel(writer=[GOOD], delay_s={"writer": 1.0})
    runner = make_runner(None, LlmWriter(model), explain_timeout_s=0.05)
    changes = [c.InterventionChange(kind="shade", site_id="s_shade_1", quantity=48)]
    out = await runner.explain(area, changes, unit_costs)
    assert out.source == "template"
    assert out.drivers == ["SHADE_GAIN"]


@pytest.mark.parametrize("kind", ["building", "plan"])
async def test_explain_route_builds_facts_from_the_engine(
    make_runner: Callable[..., Any], area: e.AreaModel, unit_costs: c.UnitCosts, kind: str
) -> None:
    changes: list[Any] = (
        [
            c.BuildingChange(
                kind="building",
                site_id="pc_1",
                design=c.BuildingDesign(floors=8, footprint_pct=60, green_pct=10, orientation_deg=0),
            )
        ]
        if kind == "building"
        else [c.InterventionChange(kind="shade", site_id="s_shade_1", quantity=48)]
    )
    model = ScriptedModel(writer=[lambda facts: WriterAnswer(paragraphs=["Fine."], drivers=[])])
    runner = make_runner(None, LlmWriter(model))
    out = await runner.explain(area, changes, unit_costs)
    assert out.source == "gemini"
    facts = model.calls[0].json["facts"]
    assert isinstance(facts, dict) and facts["mode"] == ("protect" if kind == "building" else "repair")
