"""Firestore-backed store.

WRITE-THROUGH: MemoryStore stays the live source for SSE replay; finished
RunRecords are also written to Firestore.  Every Firestore operation is
wrapped in try/except — a failure logs a warning and never breaks a run.
"""

import logging
from typing import Any

from google.cloud import firestore  # type: ignore[import-untyped]

from .base import RunRecord
from .memory import MemoryStore

log = logging.getLogger(__name__)

_COLLECTION = "runs"


def _to_doc(record: RunRecord) -> dict[str, Any]:
    return {
        "run_id": record.run_id,
        "area_id": record.area_id,
        "request": record.request.model_dump(mode="json"),
        "result": record.result.model_dump(mode="json") if record.result is not None else None,
        "finished_at": record.finished_at,
    }


class FirestoreStore:
    """Write-through store: MemoryStore is authoritative; Firestore receives finished records.

    ``_client`` is injected in tests; production uses ADC (auto-detected project on Cloud Run).
    """

    def __init__(
        self,
        project: str | None = None,
        database: str = "(default)",
        *,
        _client: Any = None,
    ) -> None:
        self._mem = MemoryStore()
        self._db: Any = _client or firestore.Client(project=project, database=database)

    def save_run(self, record: RunRecord) -> None:
        self._mem.save_run(record)
        try:
            self._db.collection(_COLLECTION).document(record.run_id).set(_to_doc(record))
            log.info("firestore write ok run=%s", record.run_id)
        except Exception:
            log.warning("firestore write failed for run %s", record.run_id, exc_info=True)

    def get_run(self, run_id: str) -> RunRecord | None:
        return self._mem.get_run(run_id)
