"""Explanations: writer model → output guard → one retry → template (agents/RULES.md "Output guard").

`write_explanation` never raises for model trouble: a timeout, a model error or a second rejection
all end in the template, marked `source="template"`. Rejections are reported to the caller's `emit`
as `guard` events so the UI can say honestly that a template replaced the model text.
"""

import asyncio
import logging
from collections.abc import Sequence
from typing import cast

import ecozone_contract as c
from ecozone_contract.common import DriverTag
from ecozone_contract.runs import GuardEvent

from .config import AgentSettings
from .errors import ModelError
from .guard import Grounding, check_explanation, grounding_from_facts
from .ports import Emit, Writer
from .templates import explain_template

log = logging.getLogger(__name__)

Facts = dict[str, object]


def _engine_drivers(facts: Facts) -> list[DriverTag]:
    return cast("list[DriverTag]", list(cast("Sequence[str]", facts.get("drivers") or [])))


def template_explanation(facts: Facts) -> c.Explanation:
    """The fallback text, filled from engine facts only."""
    return c.Explanation(paragraphs=explain_template(facts), drivers=_engine_drivers(facts), source="template")


async def write_explanation(
    writer: Writer | None, facts: Facts, settings: AgentSettings, emit: Emit | None = None
) -> c.Explanation:
    """The explanation for `facts`, from the writer if the guard accepts it, else the template."""
    if writer is None:
        return template_explanation(facts)
    grounding = grounding_from_facts(facts, round_limit=settings.max_rounds)
    try:
        async with asyncio.timeout(settings.explain_timeout_s):
            return await _attempts(writer, facts, grounding, emit)
    except TimeoutError:
        log.warning("Explanation timed out after %.0f s; using the template", settings.explain_timeout_s)
    except ModelError:
        log.exception("Explanation model call failed; using the template")
    return template_explanation(facts)


async def _attempts(writer: Writer, facts: Facts, grounding: Grounding, emit: Emit | None) -> c.Explanation:
    violations: Sequence[str] | None = None
    for attempt in (1, 2):
        out = await writer.write(facts, violations)
        violations = check_explanation(out.paragraphs, out.drivers, grounding)
        if not violations:
            drivers = cast("list[DriverTag]", out.drivers) or _engine_drivers(facts)
            return c.Explanation(paragraphs=out.paragraphs, drivers=drivers, source="gemini")
        log.warning("Output guard rejected attempt %d: %s", attempt, "; ".join(violations))
        if emit is not None:
            emit(GuardEvent(type="guard", seq=0, violations=list(violations), fallback=attempt == 2))
    return template_explanation(facts)
