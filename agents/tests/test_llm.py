"""The model side with a scripted client: proposals parse, bad answers fail soft, prompts stay number-free."""

import os
import re
from typing import Any

import pytest

import ecozone_contract as c
from ecozone_agents import AgentSettings
from ecozone_agents.errors import ModelError
from ecozone_agents.fake_llm import ScriptedModel
from ecozone_agents.llm import (
    PROMPT_VERSION,
    DesignProposals,
    GeminiClient,
    LlmProposer,
    LlmWriter,
    RepairProposals,
    WriterAnswer,
    load_prompt,
)
from ecozone_agents.ports import DesignProposal, ProposalRequest, RepairProposal

pytestmark = pytest.mark.anyio


async def test_repair_proposals_parse_and_the_model_sees_the_brief() -> None:
    answer = {
        "portfolios": [{"label": "Shade first", "changes": [{"site_id": "s_a", "quantity": 12}, {"site_id": "s_b"}]}]
    }
    model = ScriptedModel(proposer=[answer])
    proposals = await LlmProposer(model).propose(ProposalRequest("repair", 2, 4, {"budget_inr": 100.0}))
    assert proposals == [RepairProposal("Shade first", (("s_a", 12.0), ("s_b", None)))]
    [call] = model.calls
    assert call.role == "proposer" and call.json == {"budget_inr": 100.0, "round": 2, "count": 4}
    assert "Repair portfolios" in call.system


async def test_design_proposals_parse() -> None:
    answer = {"designs": [{"label": "Lower", "floors": 5, "footprint_pct": 50, "green_pct": 20, "orientation_deg": 90}]}
    model = ScriptedModel(proposer=[answer])
    proposals = await LlmProposer(model).propose(ProposalRequest("protect", 1, 4, {}))
    assert proposals == [DesignProposal("Lower", 5, 50, 20, 90)]
    assert "building designs" in model.calls[0].system


async def test_an_answer_that_does_not_fit_the_schema_is_a_model_error() -> None:
    model = ScriptedModel(proposer=[{"portfolios": "not a list"}])
    with pytest.raises(ModelError):
        await LlmProposer(model).propose(ProposalRequest("repair", 1, 4, {}))


async def test_writer_passes_facts_and_strips_blank_paragraphs() -> None:
    model = ScriptedModel(writer=[{"paragraphs": [" One. ", "  "], "drivers": ["SHADE_GAIN"]}])
    out = await LlmWriter(model).write({"a": 1}, None)
    assert out.paragraphs == ["One."] and out.drivers == ["SHADE_GAIN"]
    assert model.calls[0].json == {"facts": {"a": 1}}


def test_prompts_are_versioned_files_without_example_numbers() -> None:
    for name in ("proposer_repair", "proposer_protect", "writer"):
        text = load_prompt(name)
        assert text.strip()
        # only the scales and steps the rules state; no scores, costs or example values
        assert set(re.findall(r"\d+", text)) <= {"0", "10", "15", "100", "180"}, name
    assert PROMPT_VERSION == "v1"


def test_schemas_describe_the_structured_answers() -> None:
    assert set(RepairProposals.model_fields) == {"portfolios"}
    assert set(DesignProposals.model_fields) == {"designs"}
    assert set(WriterAnswer.model_fields) == {"paragraphs", "drivers"}


async def test_gemini_client_without_a_model_id_fails_before_any_network_call() -> None:
    client = GeminiClient(AgentSettings(_env_file=None, google_cloud_project="p", gemini_location="l"))  # pyright: ignore[reportCallIssue]
    with pytest.raises(ModelError, match="ECOZONE_MODEL_PROPOSER"):
        await client.generate(role="proposer", system="s", prompt="p", schema=WriterAnswer)
    assert client._client is None  # no Vertex client (and no credentials lookup) was created


@pytest.mark.cloud
@pytest.mark.skipif(
    os.environ.get("ECOZONE_CLOUD_TESTS") != "1", reason="needs live Google Cloud (ECOZONE_CLOUD_TESTS=1)"
)
async def test_live_gemini_returns_a_structured_answer() -> None:
    settings: Any = AgentSettings()
    assert settings.gemini_configured, "set GOOGLE_CLOUD_PROJECT, ECOZONE_GEMINI_LOCATION and both model ids"
    out = await GeminiClient(settings).generate(
        role="writer",
        system='Answer with JSON {"paragraphs": [...], "drivers": []}.',
        prompt='{"facts": {"after": {"acs": 44.4}}}',
        schema=WriterAnswer,
    )
    assert isinstance(out, WriterAnswer) and out.paragraphs
    _ = c
