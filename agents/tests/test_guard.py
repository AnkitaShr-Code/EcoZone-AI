"""The output guard: a table of accepted and rejected texts, one row per rule (agents/RULES.md).

Extend the tables with every false positive or negative found in a live run, before changing a rule.
"""

import pytest

from ecozone_agents.guard import Grounding, check_explanation, check_text, grounding_from_facts

FACTS: dict[str, object] = {
    "mode": "repair",
    "before": {"acs": 40.0, "pss": 30.0},
    "after": {"acs": 44.4, "pss": 35.6},
    "cost_inr": 925_000.0,
    "budget_inr": 1_000_000.0,
    "quick_win_cost_inr": 196_000.0,
    "quick_win_share_pct": 20.0,
    "wait_points_covered": 2,
    "counts_by_kind": {"shade": 2, "tree_row": 1},
    "interventions": [{"site_id": "s_shade_1", "name": "Bus stop 4", "quantity": 48}],
    "drivers": ["SHADE_GAIN", "GREEN_LINK"],
    "rejected": [{"site_id": "s_tree_9", "driver": "CANOPY_OBSTRUCTION", "reason": "H/W is 1.4 here."}],
    "rounds": 3,
    "reference_date": "2026-04-15",
    "parcel_ids": ["pc_1", "blk_12"],
}


@pytest.fixture
def grounding() -> Grounding:
    return grounding_from_facts(FACTS, round_limit=3)


ACCEPTED = [
    # numbers: exact, rounded, other forms
    "The area cooling score goes from 40 to 44.",
    "The area cooling score goes from 40.0 to 44.4.",
    "Footpath shade rises from 30 to 36.",
    "It uses ₹ 9.3 lakh of the ₹ 10 lakh budget.",
    "It uses ₹ 9,25,000 of the ₹ 10,00,000 budget.",
    "The quick-win share of 20% is met with ₹ 1.96 lakh.",
    "2 waiting points get shade.",
    "It combines 2 shade structures and 1 street tree row.",
    "Quantities: 48 m² of shade at Bus stop 4.",
    "The search ran 3 rounds.",
    "After round 2 nothing improved.",
    "Shade is measured at 1 pm, 3 pm and 4 pm.",
    "Shade at 1, 3 and 4 pm.",
    "Reference times are 13:00, 15:00 and 16:00.",
    "The score is 40 / 100.",
    "Scores run 0–100.",
    "1. First point\n2. Second point",
    "This is the 1st option and the 2nd option.",
    "On the reference day, 15 April, shade is shortest.",
    "H/W is 1.4 on that street.",
    # ids that exist
    "Site s_shade_1 and site s_tree_9 are discussed. Parcel pc_1 is the plot.",
    "Block 12 is the worst block.",
    # drivers that exist
    "Drivers are SHADE_GAIN and GREEN_LINK.",
    # allowed wording
    "This is recommended. The planner decides. Rejected by the ventilation check.",
    "The long side is turned 40° off the street.",
]

REJECTED = [
    # (text, a fragment of the expected violation)
    ("The score reaches 47.", "Number \"47\""),
    ("Shade rises by 6 points.", "Number \"6\""),  # a difference the model computed
    ("It costs ₹ 11 lakh.", "Number \"11\""),
    ("It costs ₹ 9.3 crore.", "Number \"9.3\""),  # wrong scale
    ("That is 99%.", "Number \"99\""),
    ("Round 5 found a better plan.", "Number \"5\""),  # beyond the round limit
    ("Shade at 7 pm is lower.", "Number \"7\""),
    ("The time 14:00 is used.", "14:00"),
    ("This is the 11th option.", "Number \"11\""),
    # forbidden units
    ("It is 5 °C cooler.", "°C"),
    ("It is 5 ℃ cooler.", "℃"),
    ("Temperature drops by 40 K.", "K"),
    ("Wind of 40 m/s.", "m/s"),
    ("Wind of 40 km/h.", "km/h"),
    ("Saves energy: 40 kWh.", "kWh"),
    ("Heat of 40 W/m².", "W/m²"),
    ("About 40 degrees Celsius.", "Celsius"),
    # approval wording
    ("The plan is approved.", "approved"),
    ("We approve this design.", "approve"),
    ("The permit should be granted.", "permit"),
    ("Permission is not needed.", "Permission"),
    ("This design is sanctioned.", "sanctioned"),
    ("Issue a work order for the site.", "work order"),
    ("The request is denied.", "denied"),
    ("The tool authorizes the build.", "authorizes"),
    # cost wording
    ("The market rate is low.", "market rate"),
    ("The price is high.", "price"),
    # drivers and ids that do not exist
    ("Driver ALBEDO_GAIN applies.", "ALBEDO_GAIN"),
    ("Driver MADE_UP_TAG applies.", "MADE_UP_TAG"),
    ("Site s_shade_77 is best.", "s_shade_77"),
    ("Parcel pc_9 is the plot.", "pc_9"),
]


@pytest.mark.parametrize("text", ACCEPTED)
def test_accepts_grounded_text(text: str, grounding: Grounding) -> None:
    assert check_text(text, grounding) == []


@pytest.mark.parametrize(("text", "fragment"), REJECTED)
def test_rejects_ungrounded_text(text: str, fragment: str, grounding: Grounding) -> None:
    violations = check_text(text, grounding)
    assert violations, text
    assert any(fragment in v for v in violations), violations


def test_violations_are_plain_language_and_deduplicated(grounding: Grounding) -> None:
    violations = check_text("It is 47 and 47 again, 5 °C.", grounding)
    assert len([v for v in violations if "47" in v]) == 1
    assert all(not v.startswith("Traceback") for v in violations)


def test_explanation_needs_the_planner_input_label_when_it_mentions_rupees(grounding: Grounding) -> None:
    assert check_explanation(["It costs ₹ 9.3 lakh."], [], grounding) == ["Costs are not labelled as planner input"]
    ok = ["It costs ₹ 9.3 lakh, from the planner's unit costs (planner input)."]
    assert check_explanation(ok, [], grounding) == []


def test_explanation_drivers_must_be_engine_drivers(grounding: Grounding) -> None:
    assert check_explanation(["Fine."], ["SHADE_GAIN"], grounding) == []
    out = check_explanation(["Fine."], ["SHADE_GAIN", "ALBEDO_GAIN"], grounding)
    assert out == ['Driver tag "ALBEDO_GAIN" was not returned by the engine']


def test_empty_explanation_is_rejected(grounding: Grounding) -> None:
    assert check_explanation([], [], grounding) == ["The explanation is empty"]
    assert check_explanation(["  "], [], grounding) == ["The explanation is empty"]


def test_estimate_wording_needs_the_planner_label(grounding: Grounding) -> None:
    assert check_explanation(["A cost estimate is shown."], [], grounding)
    assert check_explanation(["A cost estimate from planner input is shown."], [], grounding) == []


def test_grounding_collects_numbers_ids_and_drivers() -> None:
    g = grounding_from_facts(FACTS)
    assert 925_000.0 in g.values and 1.4 in g.values and 4.0 in g.values  # numbers inside strings too
    assert {"s_shade_1", "s_tree_9", "pc_1", "blk_12"} <= g.ids
    assert g.drivers == {"SHADE_GAIN", "GREEN_LINK", "CANOPY_OBSTRUCTION"}
    assert 12 in g.id_numbers
