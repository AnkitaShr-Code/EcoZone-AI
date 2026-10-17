"""Output guard: nothing reaches the planner unless every number, unit, driver and id is grounded.

Rules (agents/RULES.md "Output guard", ENGINEERING_RULES.md §7, docs/PLANNING.md "Grounding rules"):

1. Every number in digits must appear in this turn's engine values or planner input, in any of its
   displayed forms (rounded, in ₹ lakh or crore, as a percentage).
2. Also allowed: round counts up to the round limit, the reference times, the scale "0–100",
   and list ordinals up to 10.
3. No temperature, wind-speed or energy units, and no approve, deny, permit, sanction or order wording.
4. Costs are labelled planner input, and never called a price or market rate.
5. Driver tags named must be ones the engine returned; site, parcel and block ids must exist.

It is plain code with a test table (agents/tests/test_guard.py). A false positive or negative found
in a live run is added to that table before the rule changes.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import get_args

from ecozone_contract.common import DriverTag

DRIVER_TAGS = frozenset(get_args(DriverTag))

REFERENCE_TIMES = frozenset({"13:00", "15:00", "16:00"})
MAX_ORDINAL = 10
_EPS = 1e-9

# Numbers: 1,23,456 / 4,500 / 12 / 3.2. Not preceded by a word character or a dot, so ids like
# "s_tree_12" and units like "m2" never yield a stray number.
_NUMBER = re.compile(r"(?<![\w.])(?P<int>\d{1,3}(?:,\d{2,3})+|\d+)(?:\.(?P<frac>\d+))?")
_SCALE = re.compile(r"\s*(?P<word>lakhs?|crores?)\b", re.IGNORECASE)
_ID = re.compile(r"\b(?:blk|ch|wp|pc|b|s)_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*\b")
_DIGITS = re.compile(r"\d+")
_TAG_SHAPE = re.compile(r"\b[A-Z]{2,}(?:_[A-Z]+)+\b")
_TIME = re.compile(r"\b\d{1,2}:\d{2}\b")
_PM = re.compile(r"\b[134](?::00)?(?:\s*(?:,|and|&|or)\s*[134](?::00)?)*\s*(?:pm|p\.m\.)", re.IGNORECASE)
_SCALE_100 = re.compile(r"\b0\s*(?:–|-|to)\s*100\b|/\s*100\b|\bout of 100\b", re.IGNORECASE)
_LIST_MARKER = re.compile(r"^\s*(\d{1,2})[.)]\s", re.MULTILINE)
_ORDINAL = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b", re.IGNORECASE)
_ROUND_COUNT = re.compile(r"\b(\d{1,2})\s*(?:rounds?|iterations?)\b|\brounds?\s*(\d{1,2})\b", re.IGNORECASE)
_RUPEE = re.compile(r"₹|\bRs\.?\s*\d|\bINR\b|\blakhs?\b|\bcrores?\b", re.IGNORECASE)

# (pattern, name shown to the planner). Physical units the indices must never be given (ENGINEERING_RULES.md §7).
_FORBIDDEN_UNITS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"°\s*[CF]\b|℃|℉"), "°C"),
    (re.compile(r"\b(?:celsius|fahrenheit|kelvin)\b", re.IGNORECASE), "degrees Celsius"),
    (re.compile(r"\d\s*K\b"), "K"),
    (re.compile(r"\bm\s*/\s*s\b", re.IGNORECASE), "m/s"),
    (re.compile(r"\bkm\s*/\s*h\b|\bkmph\b|\bmph\b|\bknots?\b", re.IGNORECASE), "km/h"),
    (re.compile(r"\b[kM]?Wh\b|\bkW\b|\bwatts?\b|\bjoules?\b|\bBTU\b", re.IGNORECASE), "kWh"),
    (re.compile(r"\bW\s*/\s*m\s*(?:²|2)", re.IGNORECASE), "W/m²"),
]

# Never say the tool approves, denies, permits, sanctions or orders work (UI_RULES.md §6).
_APPROVAL = re.compile(
    r"\b(?:approv(?:e|es|ed|ing|al|als)|den(?:y|ies|ied|ial)|permit(?:s|ted|ting)?|permission|sanction(?:s|ed|ing)?"
    r"|work orders?|(?:issue|issues|issued|issuing)\s+(?:an?\s+)?orders?|orders?\s+(?:the|this|that|to)\b"
    r"|authori[sz](?:e|es|ed|ation)|licen[cs]e[sd]?)\b",
    re.IGNORECASE,
)
_PRICE = re.compile(r"\bmarket\s+(?:rates?|prices?)\b|\bprices?\b|\bpriced\b", re.IGNORECASE)
_ESTIMATE = re.compile(r"\bestimates?\b|\bestimated\b", re.IGNORECASE)


@dataclass(frozen=True)
class Grounding:
    """What this turn's answer may cite: engine values and planner input, flattened."""

    values: tuple[float, ...]
    ids: frozenset[str]
    drivers: frozenset[str]
    id_numbers: frozenset[int] = field(default_factory=frozenset[int])
    round_limit: int = 3


def grounding_from_facts(facts: Mapping[str, object], *, round_limit: int = 3) -> Grounding:
    """Collect every number, id and driver tag in `facts` (the dict the writer was given)."""
    values: list[float] = []
    ids: set[str] = set()
    drivers: set[str] = set()

    def walk(node: object, key: str = "") -> None:
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, int | float):
            values.append(float(node))
        elif isinstance(node, str):
            values.extend(n.value for n in _numbers(node))
            ids.update(_ID.findall(node))
            if key in ("drivers", "driver") and node in DRIVER_TAGS:
                drivers.add(node)
        elif isinstance(node, Mapping):
            for k, v in node.items():  # pyright: ignore[reportUnknownVariableType]
                ids.update(_ID.findall(str(k)))  # pyright: ignore[reportUnknownArgumentType]
                walk(v, str(k))  # pyright: ignore[reportUnknownArgumentType]
        elif isinstance(node, Iterable):
            for v in node:  # pyright: ignore[reportUnknownVariableType]
                walk(v, key)

    walk(facts)
    id_numbers = {int(d) for i in ids for d in _DIGITS.findall(i)}
    return Grounding(tuple(values), frozenset(ids), frozenset(drivers), frozenset(id_numbers), round_limit)


@dataclass(frozen=True)
class _Number:
    value: float
    decimals: int
    scale: float
    start: int
    end: int
    text: str


def _numbers(text: str) -> list[_Number]:
    found: list[_Number] = []
    for m in _NUMBER.finditer(text):
        frac = m.group("frac") or ""
        value = float(m.group("int").replace(",", "") + ("." + frac if frac else ""))
        scale_match = _SCALE.match(text, m.end())
        scale = 1.0
        if scale_match:
            scale = 1e5 if scale_match.group("word").lower().startswith("lakh") else 1e7
        found.append(_Number(value, len(frac), scale, m.start(), m.end(), m.group(0)))
    return found


def _spans(pattern: re.Pattern[str], text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in pattern.finditer(text)]


def _inside(n: _Number, spans: Sequence[tuple[int, int]]) -> bool:
    return any(s <= n.start and n.end <= e for s, e in spans)


def _context_allowed(text: str, grounding: Grounding) -> tuple[list[tuple[int, int]], list[str]]:
    """Spans whose numbers are allowed by context, plus violations found while scanning them."""
    spans: list[tuple[int, int]] = []
    problems: list[str] = []
    pm = _spans(_PM, text)
    spans += pm
    for m in _TIME.finditer(text):
        spans.append((m.start(), m.end()))
        if m.group(0) not in REFERENCE_TIMES and not any(s <= m.start() and m.end() <= e for s, e in pm):
            problems.append(f'Time "{m.group(0)}" is not one of the reference times (1 pm, 3 pm, 4 pm)')
    spans += _spans(_SCALE_100, text)
    for m in _LIST_MARKER.finditer(text):
        if int(m.group(1)) <= MAX_ORDINAL:
            spans.append((m.start(1), m.end(1)))
    for m in _ORDINAL.finditer(text):
        if int(m.group(1)) <= MAX_ORDINAL:
            spans.append((m.start(1), m.end(1)))
    for m in _ROUND_COUNT.finditer(text):
        group = 1 if m.group(1) else 2
        if int(m.group(group)) <= grounding.round_limit:
            spans.append((m.start(group), m.end(group)))
    return spans, problems


def _grounded(n: _Number, grounding: Grounding) -> bool:
    value = n.value * n.scale
    tolerance = 0.5 * 10 ** (-n.decimals) * n.scale + _EPS
    if any(abs(a - value) <= tolerance for a in grounding.values):
        return True
    return n.scale == 1.0 and n.decimals == 0 and int(n.value) in grounding.id_numbers


def check_text(text: str, grounding: Grounding) -> list[str]:
    """Violations in one string, in plain language; empty when the text is grounded."""
    violations: list[str] = []
    spans, problems = _context_allowed(text, grounding)
    violations += problems
    for n in _numbers(text):
        if _inside(n, spans) or _grounded(n, grounding):
            continue
        violations.append(f'Number "{n.text}" is not in the engine results or planner input')
    for pattern, name in _FORBIDDEN_UNITS:
        if m := pattern.search(text):
            violations.append(f'Unit "{m.group(0).strip()}" is not allowed ({name}); the indices are 0–100 scores')
    if m := _APPROVAL.search(text):
        violations.append(f'Wording "{m.group(0)}" is not allowed; the tool supports the decision, the planner decides')
    if m := _PRICE.search(text):
        violations.append(f'Wording "{m.group(0)}" is not allowed; costs come from planner unit costs')
    for tag in _TAG_SHAPE.findall(text):
        if tag not in grounding.drivers:
            violations.append(f'Driver tag "{tag}" was not returned by the engine')
    for identifier in _ID.findall(text):
        if identifier not in grounding.ids:
            violations.append(f'Id "{identifier}" is not in this area')
    return list(dict.fromkeys(violations))


def check_explanation(paragraphs: Sequence[str], drivers: Sequence[str], grounding: Grounding) -> list[str]:
    """The whole answer: every paragraph, the driver list and the cost label."""
    if not paragraphs or not any(p.strip() for p in paragraphs):
        return ["The explanation is empty"]
    violations: list[str] = []
    for paragraph in paragraphs:
        violations += check_text(paragraph, grounding)
    for tag in drivers:
        if tag not in grounding.drivers:
            violations.append(f'Driver tag "{tag}" was not returned by the engine')
    whole = "\n".join(paragraphs)
    if _RUPEE.search(whole) and "planner" not in whole.lower():
        violations.append("Costs are not labelled as planner input")
    if _ESTIMATE.search(whole) and "planner" not in whole.lower():
        violations.append('"Estimate" is used without saying the costs are planner input')
    return list(dict.fromkeys(violations))
