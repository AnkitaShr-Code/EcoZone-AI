"""Plain templates filled from engine facts: the fallback when the output guard rejects the model twice.

Every sentence here is built only from `facts.py` values, so a template always passes the guard
(tested in tests/test_templates.py). Wording follows app/UI_RULES.md §6 and mirrors the UI's mock
explanations (app/src/api/mock/explainMock.ts), so a fallback reads like a normal answer.
"""

from typing import cast

from .text import (
    CAVEAT,
    INDEX_WORDS,
    count_label,
    fmt_inr,
    fmt_pct,
    fmt_score,
    join_words,
)

Facts = dict[str, object]
Block = dict[str, float]

COST_NOTE = "Costs use the unit costs entered by the planner (planner input)."


def _block(facts: Facts, key: str) -> Block:
    return cast(Block, facts[key])


def _drivers_sentence(facts: Facts) -> str | None:
    labels = cast("dict[str, str]", facts.get("driver_labels") or {})
    if not labels:
        return None
    return f"Main drivers: {join_words(list(labels.values()))}."


def explain_template(facts: Facts) -> list[str]:
    """Template paragraphs for either mode."""
    return protect_template(facts) if facts.get("mode") == "protect" else repair_template(facts)


def repair_template(facts: Facts) -> list[str]:
    before, after = _block(facts, "before"), _block(facts, "after")
    cost = fmt_inr(cast(float, facts["cost_inr"]))
    movement = "raises" if after["acs"] > before["acs"] else "moves"
    spend = (
        f"using {cost} of the {fmt_inr(cast(float, facts['budget_inr']))} budget"
        if "budget_inr" in facts
        else f"at a cost of {cost}"
    )
    paragraphs = [
        f"This plan {movement} the area cooling score from {fmt_score(before['acs'])} "
        f"to {fmt_score(after['acs'])}, {spend}. "
        f"{COST_NOTE}"
    ]

    counts = cast("dict[str, int]", facts.get("counts_by_kind") or {})
    mix = [count_label(kind, n) for kind, n in counts.items()]
    shade = f"Footpath shade goes from {fmt_score(before['pss'])} to {fmt_score(after['pss'])}"
    covered = cast(int, facts.get("wait_points_covered") or 0)
    if covered:
        shade += f", and {covered} waiting {'point gets' if covered == 1 else 'points get'} shade at the entrance"
    paragraphs.append((f"It combines {join_words(mix)}. " if mix else "") + shade + ".")

    quick = cast(float, facts.get("quick_win_cost_inr") or 0)
    if "quick_win_share_pct" in facts and quick:
        share = fmt_pct(cast(float, facts["quick_win_share_pct"]))
        years = ""
        if "tree_row" in counts:
            years = " Street trees give shade only after a few years."
        paragraphs.append(
            f"{fmt_inr(quick)} goes to work that helps this summer, meeting the {share} quick-win share.{years}"
        )

    total = cast(int, facts.get("rejected_total") or 0)
    if total:
        paragraphs.append(
            f"{total} candidate {'site was' if total == 1 else 'sites were'} rejected by the ventilation check and "
            "left out of the plan. Where canopy would block the breeze, a shade structure works better."
        )

    greedy = cast("dict[str, float] | None", facts.get("greedy"))
    if greedy is not None:
        if facts.get("plan_source") == "greedy":
            paragraphs.append(
                "No AI plan beat the simple ranking baseline, so the baseline plan is shown "
                f"({fmt_score(greedy['acs'])})."
            )
        else:
            paragraphs.append(
                f"The simple ranking baseline reaches {fmt_score(greedy['acs'])}; "
                f"this plan reaches {fmt_score(after['acs'])}."
            )

    if (drivers := _drivers_sentence(facts)) is not None:
        paragraphs.append(drivers)
    paragraphs.append(CAVEAT)
    return paragraphs


def protect_template(facts: Facts) -> list[str]:
    paragraphs: list[str] = []
    parcel = cast("dict[str, object]", facts["parcel"])
    proposal = _block(facts, "proposal")
    risk = cast("dict[str, object] | None", facts.get("risk"))
    street = ""
    width = parcel.get("road_width_m")
    floors = int(proposal["floors"])
    if width is not None:
        street = f" A {floors}-floor building faces a {fmt_score(cast(float, width))} m street."
    if risk is not None:
        words, direction = INDEX_WORDS[cast(str, risk["index"])]
        label = cast(str, risk["label"]).lower()
        paragraphs.append(
            f"As proposed, the worst effect is on {words}: it {direction} by {fmt_score(cast(float, risk['change']))} "
            f"on the parcel's block ({label} risk).{street}"
        )
    else:
        paragraphs.append(f"The engine returned no risk label for this design.{street}".strip())

    options = cast("list[dict[str, object]]", facts.get("options") or [])
    by_key = {cast(str, o["key"]): o for o in options}
    if "A" in by_key and "B" in by_key and "C" in by_key:
        a, b, c = by_key["A"], by_key["B"], by_key["C"]
        a_change, b_change, c_change = (cast(float, o["worst_change"]) for o in (a, b, c))
        keep = cast(float, facts.get("keep_floor_area_pct") or 0)
        if fmt_score(b_change) != fmt_score(a_change):
            paragraphs.append(
                f"Option B keeps {fmt_pct(cast(float, b['floor_area_pct']))} of the floor area "
                "and brings the worst change "
                f"from {fmt_score(a_change)} to {fmt_score(b_change)}."
            )
        else:
            paragraphs.append(
                f"No design that keeps at least {fmt_pct(keep)} of the floor area "
                "lowers the worst change on this street. "
                "Lower that share to see more options."
            )
        paragraphs.append(
            f"Option C keeps {fmt_pct(cast(float, c['floor_area_pct']))} of the floor area and brings it to "
            f"{fmt_score(c_change)}. The planner decides which trade-off fits."
        )
    else:
        after, before = _block(facts, "after"), _block(facts, "before")
        if fmt_score(after["pss"]) != fmt_score(before["pss"]):
            paragraphs.append(
                f"The building also changes footpath shade across the area, from {fmt_score(before['pss'])} "
                f"to {fmt_score(after['pss'])}."
            )
        worse = cast(int, facts.get("blocks_worse") or 0)
        if worse:
            paragraphs.append(f"{worse} existing {'block loses' if worse == 1 else 'blocks lose'} cooling score.")

    if (drivers := _drivers_sentence(facts)) is not None:
        paragraphs.append(drivers)
    paragraphs.append(CAVEAT)
    return paragraphs
