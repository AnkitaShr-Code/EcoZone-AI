"""The model side: prompts, structured answers, the Gemini client and the LLM-backed proposer and writer.

Gemini runs on Vertex AI with Application Default Credentials only (ENGINEERING_RULES.md §1.8):
the client takes a project and a location, never a key. Models are named by settings, so the
Flash and Pro ids can change without code changes (WP3 verifies them).
"""

import json
import logging
from collections.abc import Sequence
from importlib import resources
from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel

from .config import AgentSettings
from .errors import ModelError
from .ports import (
    DesignProposal,
    ModelClient,
    ModelOut,
    Proposal,
    ProposalRequest,
    RepairProposal,
    Role,
    WriterOutput,
)

log = logging.getLogger(__name__)

PROMPT_VERSION = "v1"


def load_prompt(name: str) -> str:
    """Prompts are files, versioned by filename suffix (agents/RULES.md)."""
    return resources.files("ecozone_agents").joinpath("prompts", f"{name}_{PROMPT_VERSION}.md").read_text("utf-8")


# ---------- structured answers (the response schemas) ----------


class PortfolioChange(BaseModel):
    site_id: str
    quantity: float | None = None


class PortfolioItem(BaseModel):
    label: str
    changes: list[PortfolioChange]


class RepairProposals(BaseModel):
    portfolios: list[PortfolioItem]


class DesignItem(BaseModel):
    label: str
    floors: float
    footprint_pct: float
    green_pct: float
    orientation_deg: float


class DesignProposals(BaseModel):
    designs: list[DesignItem]


class WriterAnswer(BaseModel):
    paragraphs: list[str]
    drivers: list[str]


# ---------- Gemini on Vertex AI ----------


class GeminiClient:
    """`ModelClient` over google-genai with the Vertex AI backend. Never reads or accepts an API key."""

    def __init__(self, settings: AgentSettings) -> None:
        self._settings = settings
        self._client: genai.Client | None = None

    def _vertex(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(
                vertexai=True, project=self._settings.google_cloud_project, location=self._settings.gemini_location
            )
        return self._client

    async def generate(self, *, role: Role, system: str, prompt: str, schema: type[ModelOut]) -> ModelOut:
        s = self._settings
        model = s.model_proposer if role == "proposer" else s.model_writer
        if not model:
            raise ModelError(f"No Gemini model is set for the {role}. Set ECOZONE_MODEL_{role.upper()}.")
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=s.proposer_temperature if role == "proposer" else s.writer_temperature,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel(s.thinking_level.upper()))
            if s.thinking_level
            else None,
        )
        try:
            response = await self._vertex().aio.models.generate_content(model=model, contents=prompt, config=config)
            if not response.text:
                raise ModelError("The model returned no text.")
            return schema.model_validate_json(response.text)
        except ModelError:
            raise
        except Exception as exc:  # network, quota, credentials or schema: all fail soft
            log.warning("Gemini call failed (%s)", type(exc).__name__, exc_info=True)
            raise ModelError(f"The model call failed ({type(exc).__name__}).") from exc


# ---------- LLM-backed proposer and writer ----------


class LlmProposer:
    """Asks the Flash tier model for candidates, given the compact brief, never geometry."""

    def __init__(self, client: ModelClient) -> None:
        self._client = client
        self._system = {"repair": load_prompt("proposer_repair"), "protect": load_prompt("proposer_protect")}

    async def propose(self, request: ProposalRequest) -> list[Proposal]:
        prompt = json.dumps({**request.brief, "round": request.round, "count": request.count}, ensure_ascii=False)
        system = self._system[request.mode]
        if request.mode == "repair":
            repair = await self._client.generate(role="proposer", system=system, prompt=prompt, schema=RepairProposals)
            return [
                RepairProposal(p.label, tuple((ch.site_id, ch.quantity) for ch in p.changes)) for p in repair.portfolios
            ]
        designs = await self._client.generate(role="proposer", system=system, prompt=prompt, schema=DesignProposals)
        return [
            DesignProposal(d.label, d.floors, d.footprint_pct, d.green_pct, d.orientation_deg) for d in designs.designs
        ]


class LlmWriter:
    """Asks the Pro tier model for the explanation; the output guard judges the answer, not this class."""

    def __init__(self, client: ModelClient) -> None:
        self._client = client
        self._system = load_prompt("writer")

    async def write(self, facts: dict[str, object], violations: Sequence[str] | None) -> WriterOutput:
        prompt: dict[str, Any] = {"facts": facts}
        if violations:
            prompt["rejected_previous_answer_because"] = list(violations)
        answer = await self._client.generate(
            role="writer",
            system=self._system,
            prompt=json.dumps(prompt, ensure_ascii=False),
            schema=WriterAnswer,
        )
        return WriterOutput(
            paragraphs=[p.strip() for p in answer.paragraphs if p.strip()], drivers=list(answer.drivers)
        )
