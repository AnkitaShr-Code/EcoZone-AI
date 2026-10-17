"""Plain-language words and number formats for planner-facing text.

The formats match app/src/lib/format.ts and meta.ts (UI_RULES.md §6): scores as whole numbers,
money as "₹ 3.2 lakh", sentence case, no physical units. Labels are copy, not scores.
"""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

KIND_LABEL: dict[str, tuple[str, str]] = {
    "tree_row": ("street tree row", "street tree rows"),
    "shade": ("shade structure", "shade structures"),
    "depave": ("depave site", "depave sites"),
    "pocket_green": ("pocket green", "pocket greens"),
    "cool_roof": ("cool roof block", "cool roof blocks"),
}

DRIVER_LABEL: dict[str, str] = {
    "IMPERVIOUS_HIGH": "mostly paved",
    "LOW_SHADE": "little afternoon shade",
    "WAIT_POINTS": "people wait nearby",
    "DENSE_LOW_RISE": "dense low-rise housing",
    "LOW_GREEN": "little greenery",
    "SHADE_GAIN": "adds footpath shade",
    "GREEN_LINK": "links green patches",
    "IMPERVIOUS_LOSS": "removes paving",
    "ALBEDO_GAIN": "reflects more sunlight",
    "WAIT_POINT_COVERED": "shades a waiting point",
    "CANOPY_OBSTRUCTION": "canopy would block the breeze",
    "OBSTRUCTION": "tall against the street width",
    "ORIENTATION": "turned across the wind",
    "BUILT_RUN": "longer built-up run",
    "IMPERVIOUS_GAIN": "adds paving and roof",
    "MASS_GAIN": "adds building mass",
    "GREEN_LOSS": "removes open green",
    "GREEN_ISOLATED": "green left isolated",
    "SHADE_LOSS": "removes footpath shade",
}

INDEX_WORDS: dict[str, tuple[str, str]] = {
    "vci": ("ventilation", "falls"),
    "hei": ("heat exposure", "rises"),
    "gcs": ("green connectivity", "falls"),
    "pss": ("footpath shade", "falls"),
}

CAVEAT = "The indices are 0–100 screening scores for comparing options, not measurements. The planner decides."


def half_up(value: float, places: int = 0) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def fmt_score(value: float) -> str:
    """Index score, 0–100, as a whole number: "64"."""
    return str(int(half_up(value)))


def fmt_pct(value: float) -> str:
    return f"{int(half_up(value))}%"


def _trim(n: float) -> str:
    text = f"{half_up(n, 0 if n >= 100 else 1)}"
    return text[:-2] if text.endswith(".0") else text


def _indian_grouping(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join([*groups, tail])


def fmt_inr(value: float) -> str:
    """Rupees in lakh or crore for large values: "₹ 25 lakh", "₹ 3.2 lakh", "₹ 4,500"."""
    if value >= 1e7:
        return f"₹ {_trim(value / 1e7)} crore"
    if value >= 1e5:
        return f"₹ {_trim(value / 1e5)} lakh"
    return f"₹ {_indian_grouping(int(half_up(value)))}"


def join_words(items: Sequence[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"


def count_label(kind: str, count: int) -> str:
    singular, plural = KIND_LABEL.get(kind, (kind.replace("_", " "), kind.replace("_", " ") + "s"))
    return f"{count} {singular if count == 1 else plural}"
