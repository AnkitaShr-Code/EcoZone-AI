"""Live Gemini runs (needs Vertex credentials): `ECOZONE_LLM=gemini uv run pytest evals -m live`.

Same table as the fake-LLM module, written to the results file under `gemini_vs_greedy.live`. Not part of the offline
suite and never required: it is skipped unless the marker is selected, `ECOZONE_LLM=gemini` is set and the Vertex
settings (GOOGLE_CLOUD_PROJECT, ECOZONE_GEMINI_LOCATION, ECOZONE_MODEL_PROPOSER, ECOZONE_MODEL_WRITER) are present.
"""

import os

import pytest

from ecozone_agents import AgentSettings
from evalkit.bench import Bench
from evalkit.cases import AreaCases
from evalkit.compare import compare
from evalkit.results import Recorder

pytestmark = pytest.mark.live


def _live_settings() -> AgentSettings:
    if os.environ.get("ECOZONE_LLM") != "gemini":
        pytest.skip("live Gemini evals need ECOZONE_LLM=gemini")
    settings = AgentSettings()  # pyright: ignore[reportCallIssue]  (reads ECOZONE_* and GOOGLE_CLOUD_PROJECT)
    if not settings.gemini_configured:
        pytest.skip("Gemini is not configured: set GOOGLE_CLOUD_PROJECT, ECOZONE_GEMINI_LOCATION and both model ids")
    return settings


def _record_settings(rec: Recorder, settings: AgentSettings) -> None:
    rec.measure(
        "gemini_vs_greedy.live_settings",
        "gemini",
        {
            "proposer": settings.model_proposer,
            "writer": settings.model_writer,
            "location": settings.gemini_location,
            "thinking_level": settings.thinking_level,
            "max_rounds": settings.max_rounds,
            "proposals_per_round": settings.proposals_per_round,
            "proposer_timeout_s": settings.proposer_timeout_s,
            "search_time_limit_s": settings.search_time_limit_s,
        },
        "settings the live runs used",
    )


def test_live_gemini_vs_greedy_per_case(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    settings = _live_settings()
    _record_settings(rec, settings)
    for rc in cases.repair:
        run = bench._drive(bench.repair_request(rc), settings)  # pyright: ignore[reportPrivateUsage]
        row = compare(bench, rc, run)
        row.update(budget_inr=rc.budget_inr, quick_win_share_pct=rc.quick_win_share_pct, proposer="gemini")
        rec.measure("gemini_vs_greedy.live", rc.id, row, "live Gemini on Vertex AI; no pass mark")


def test_live_protect_options(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    settings = _live_settings()
    for pc in cases.protect:
        run = bench._drive(bench.protect_request(pc), settings)  # pyright: ignore[reportPrivateUsage]
        options = run.result.options or []
        rec.measure(
            "protect_search.live",
            pc.id,
            {o.key: {"worst_change": o.candidate.score, "floor_area_pct": o.candidate.floor_area_pct} for o in options},
            "live Gemini on Vertex AI",
        )
        assert [o.key for o in options] == ["A", "B", "C"]
