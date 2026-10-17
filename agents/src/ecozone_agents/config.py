"""Agent settings from environment variables, read by one class (ENGINEERING_RULES.md §10).

Gemini runs on Vertex AI with Application Default Credentials only; there is no API key setting
and none is ever read. Round limits and thresholds come from docs/PLANNING.md ("Portfolio search
loop", "Design search loop"); timeouts from ENGINEERING_RULES.md §8 and api/RULES.md.
"""

from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ECOZONE_", env_file=".env", extra="ignore", populate_by_name=True)

    llm: Literal["gemini", "fake"] = "gemini"
    """`fake` runs the offline rule proposer and template text, with no cloud calls at all."""
    google_cloud_project: str | None = Field(default=None, validation_alias=AliasChoices("GOOGLE_CLOUD_PROJECT"))
    gemini_location: str | None = None
    model_proposer: str | None = None
    """Flash tier Vertex model id for search proposals (WP3 verifies it)."""
    model_writer: str | None = None
    """Pro tier Vertex model id for explanations (WP3 verifies it)."""

    max_rounds: int = Field(default=2, ge=1)
    min_rounds: int = Field(default=2, ge=1)
    """The judge never stops on "no improvement" before this round, so the planner always sees a refinement."""
    proposals_per_round: int = Field(default=4, ge=1)
    repair_threshold: float = 0.5
    """Stop when no portfolio beats the best by more than this many ACS points."""
    protect_threshold: float = 2.0
    """Stop when no design beats the best by more than this many points of the worst change."""
    search_time_limit_s: float = 300.0
    proposer_timeout_s: float = 120.0
    explain_timeout_s: float = 20.0
    max_sites_in_prompt: int = 120
    rejected_shown: int = 3
    proposer_temperature: float = 0.7
    writer_temperature: float = 0.2

    @property
    def gemini_configured(self) -> bool:
        """True when every Vertex setting the real client needs is present (never reads a secret)."""
        return all((self.google_cloud_project, self.gemini_location, self.model_proposer, self.model_writer))
