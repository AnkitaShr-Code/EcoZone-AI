"""Template fallback text: filled from engine facts only, and always accepted by the output guard."""

from typing import Any

import pytest

import ecozone_contract as c
import ecozone_engine as e
from ecozone_agents import to_contract as tc
from ecozone_agents.catalog import describe_sites
from ecozone_agents.explain import template_explanation
from ecozone_agents.facts import protect_facts, repair_facts
from ecozone_agents.guard import check_explanation, grounding_from_facts
from ecozone_agents.text import fmt_inr, fmt_pct, fmt_score, join_words


@pytest.mark.parametrize(
    ("value", "expected"),
    [(63.4, "63"), (63.5, "64"), (44.45, "44"), (0.0, "0")],
)
def test_score_format_matches_the_ui(value: float, expected: str) -> None:
    assert fmt_score(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (4500, "₹ 4,500"),
        (99_999, "₹ 99,999"),
        (320_000, "₹ 3.2 lakh"),
        (2_500_000, "₹ 25 lakh"),
        (925_000, "₹ 9.3 lakh"),
        (12_345_678, "₹ 1.2 crore"),
        (1_234_567, "₹ 12.3 lakh"),
        (150_000, "₹ 1.5 lakh"),
    ],
)
def test_rupee_format_matches_the_ui(value: float, expected: str) -> None:
    assert fmt_inr(value) == expected


def test_small_helpers() -> None:
    assert fmt_pct(79.6) == "80%"
    assert join_words(["a", "b", "c"]) == "a, b and c"
    assert join_words(["a"]) == "a"


def repair(engine: Any, area: e.AreaModel, unit_costs: c.UnitCosts, ids: list[str], **extra: Any) -> dict[str, object]:
    costs = tc.engine_unit_costs(unit_costs)
    sites = describe_sites(engine, area)
    changes = [e.Change(sites[i].kind, i, sites[i].quantity) for i in ids]
    result = engine.rescore(area, changes, costs)
    return repair_facts(result=result, changes=changes, sites=sites, unit_costs=unit_costs, **extra)


def test_repair_template_reads_like_the_ui_mock_and_passes_the_guard(
    engine: Any, area: e.AreaModel, unit_costs: c.UnitCosts
) -> None:
    facts = repair(
        engine,
        area,
        unit_costs,
        ["s_shade_2", "s_tree_1", "s_dep_1"],
        budget_inr=700_000,
        quick_win_share_pct=20,
        greedy=(44.2, 542_000),
        plan_source="gemini",
        gemini_beat_greedy=True,
        rejected=[c.RejectedOption(site_id="s_tree_9", driver="CANOPY_OBSTRUCTION", reason="Too narrow.")],
        rejected_total=1,
        rounds=2,
    )
    paragraphs = template_explanation(facts).paragraphs
    text = "\n".join(paragraphs)
    assert "raises the area cooling score from 40 to 46" in text
    assert "using ₹ 5.8 lakh of the ₹ 7 lakh budget" in text
    assert "It combines 1 depave site, 1 shade structure and 1 street tree row." in text
    assert "₹ 4.7 lakh goes to work that helps this summer, meeting the 20% quick-win share" in text
    assert "1 candidate site was rejected by the ventilation check" in text
    assert "The simple ranking baseline reaches 44; this plan reaches 46." in text
    assert "planner input" in text
    assert check_explanation(paragraphs, [], grounding_from_facts(facts)) == []


def test_repair_template_when_greedy_won(engine: Any, area: e.AreaModel, unit_costs: c.UnitCosts) -> None:
    facts = repair(
        engine, area, unit_costs, ["s_shade_2"], budget_inr=700_000, greedy=(43.0, 196_000), plan_source="greedy"
    )
    template = template_explanation(facts)
    assert template.source == "template"
    assert any("No AI plan beat the simple ranking baseline" in p for p in template.paragraphs)
    assert check_explanation(template.paragraphs, template.drivers, grounding_from_facts(facts)) == []


def test_repair_template_for_the_explain_route_has_no_budget(
    engine: Any, area: e.AreaModel, unit_costs: c.UnitCosts
) -> None:
    facts = repair(engine, area, unit_costs, ["s_shade_1"])
    template = template_explanation(facts)
    assert "at a cost of ₹ 2.4 lakh" in template.paragraphs[0]
    assert template.drivers == ["SHADE_GAIN"]
    assert check_explanation(template.paragraphs, template.drivers, grounding_from_facts(facts)) == []


def test_protect_template_for_a_proposal_alone(engine: Any, area: e.AreaModel, unit_costs: c.UnitCosts) -> None:
    design = c.BuildingDesign(floors=8, footprint_pct=60, green_pct=10, orientation_deg=0)
    result = engine.rescore(area, [tc.building_change("pc_1", design)], tc.engine_unit_costs(unit_costs))
    facts = protect_facts(proposal=design, result=result, parcel=None, parcel_id="pc_1")
    template = template_explanation(facts)
    assert template.paragraphs[0].startswith("As proposed, the worst effect is on ventilation: it falls by 18")
    assert "(moderate risk)" in template.paragraphs[0]
    assert "2 existing blocks lose cooling score." in template.paragraphs
    assert template.drivers == ["OBSTRUCTION", "SHADE_GAIN"]
    assert check_explanation(template.paragraphs, template.drivers, grounding_from_facts(facts)) == []
