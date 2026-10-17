"""Runner wiring: settings, which runner is built, explain routing and the SearchRunner shape."""

import inspect
from collections.abc import Callable
from typing import Any

import pytest

import ecozone_contract as c
import ecozone_engine as e
from ecozone_agents import AgentSettings, AgentsRunner, build_runner
from ecozone_agents.llm import LlmProposer, LlmWriter
from ecozone_agents.offline import RuleProposer

pytestmark = pytest.mark.anyio


def test_settings_read_the_documented_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
    monkeypatch.setenv("ECOZONE_GEMINI_LOCATION", "asia-south1")
    monkeypatch.setenv("ECOZONE_MODEL_PROPOSER", "flash-model")
    monkeypatch.setenv("ECOZONE_MODEL_WRITER", "pro-model")
    s = AgentSettings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert (s.google_cloud_project, s.gemini_location, s.model_proposer, s.model_writer) == (
        "proj",
        "asia-south1",
        "flash-model",
        "pro-model",
    )
    assert s.gemini_configured and s.llm == "gemini"
    assert (s.max_rounds, s.proposals_per_round, s.explain_timeout_s) == (3, 4, 20.0)


def test_there_is_no_api_key_setting() -> None:
    assert not [name for name in AgentSettings.model_fields if "key" in name or "secret" in name or "token" in name]


def test_gemini_without_settings_gives_no_runner(engine: Any, unit_costs: c.UnitCosts) -> None:
    settings = AgentSettings(_env_file=None, llm="gemini", google_cloud_project=None)  # pyright: ignore[reportCallIssue]
    assert build_runner(engine, unit_costs, settings) is None


def test_gemini_with_settings_builds_the_real_clients_without_touching_the_network(
    engine: Any, unit_costs: c.UnitCosts
) -> None:
    settings = AgentSettings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        llm="gemini",
        google_cloud_project="p",
        gemini_location="l",
        model_proposer="flash",
        model_writer="pro",
    )
    runner = build_runner(engine, unit_costs, settings)
    assert isinstance(runner, AgentsRunner)
    assert isinstance(runner.proposer, LlmProposer) and isinstance(runner.writer, LlmWriter)


def test_fake_mode_builds_the_offline_runner(engine: Any, unit_costs: c.UnitCosts) -> None:
    settings = AgentSettings(_env_file=None, llm="fake")  # pyright: ignore[reportCallIssue]
    runner = build_runner(engine, unit_costs, settings)
    assert isinstance(runner, AgentsRunner)
    assert isinstance(runner.proposer, RuleProposer) and runner.writer is None


def test_runner_has_the_shape_of_apis_search_runner() -> None:
    search = inspect.signature(AgentsRunner.search)
    explain = inspect.signature(AgentsRunner.explain)
    assert list(search.parameters) == ["self", "area", "request", "emit"]
    assert list(explain.parameters) == ["self", "area", "changes", "unit_costs"]
    assert inspect.iscoroutinefunction(AgentsRunner.search) and inspect.iscoroutinefunction(AgentsRunner.explain)


async def test_single_site_results_are_cached_per_bundle_and_unit_costs(
    make_runner: Callable[..., Any],
    engine: Any,
    area: e.AreaModel,
    repair_request: c.runs.RepairSearchRequest,  # pyright: ignore[reportAttributeAccessIssue]
    emit: Any,
) -> None:
    runner = make_runner(RuleProposer(), max_rounds=1)
    await runner.search(area, repair_request, emit)
    first = engine.single_site_calls
    await runner.search(area, repair_request, emit)
    assert first == len(engine.sites) and engine.single_site_calls == first


async def test_explain_error_from_the_engine_propagates_for_the_api_to_map(
    make_runner: Callable[..., Any], area: e.AreaModel, unit_costs: c.UnitCosts
) -> None:
    runner = make_runner(RuleProposer())
    with pytest.raises(e.UnknownSiteError):
        await runner.explain(area, [c.InterventionChange(kind="shade", site_id="s_nope", quantity=1)], unit_costs)
