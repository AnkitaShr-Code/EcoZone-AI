"""The Store protocol (api/RULES.md). Writes are best effort and never fail a response."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ecozone_contract import SearchRequest, SearchResult


@dataclass(frozen=True)
class RunRecord:
    """A finished agent run and its best result (None when it ended without one)."""

    run_id: str
    area_id: str
    request: SearchRequest
    result: SearchResult | None
    finished_at: datetime


class Store(Protocol):
    def save_run(self, record: RunRecord) -> None: ...

    def get_run(self, run_id: str) -> RunRecord | None: ...
