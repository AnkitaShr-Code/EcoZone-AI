"""In-memory store for local runs and tests; lost on restart."""

from .base import RunRecord


class MemoryStore:
    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}

    def save_run(self, record: RunRecord) -> None:
        self._runs[record.run_id] = record

    def get_run(self, run_id: str) -> RunRecord | None:
        return self._runs.get(run_id)
