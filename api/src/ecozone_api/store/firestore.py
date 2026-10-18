"""Firestore-backed store.

WRITE-THROUGH: MemoryStore stays the live source for SSE replay; finished
RunRecords are also written to Firestore.  Every Firestore operation is
best-effort: failures log a warning and never break a run.

When save_run is called from an async context (the normal path via RunManager),
the blocking Firestore .set() runs in the default thread-pool executor so it
cannot stall the event loop or delay the SSE done event.  In a synchronous
context (tests, CLI) it runs inline.
"""

import asyncio
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
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running (sync context: tests, CLI) — write inline.
            try:
                self._write(record)
            except Exception:
                log.warning("firestore write failed for run %s", record.run_id, exc_info=True)
            return
        # Async context: hand the blocking network call to the thread pool so
        # the event loop — and any waiting SSE clients — are not stalled.
        fut = loop.run_in_executor(None, self._write, record)
        fut.add_done_callback(lambda f: self._on_write_done(f, record.run_id))

    def _write(self, record: RunRecord) -> None:
        self._db.collection(_COLLECTION).document(record.run_id).set(_to_doc(record))
        log.info("firestore write ok run=%s", record.run_id)

    def _on_write_done(self, future: Any, run_id: str) -> None:
        try:
            exc = future.exception()
        except (asyncio.CancelledError, Exception):
            return
        if exc is not None:
            log.warning("firestore write failed for run %s: %s", run_id, exc)

    def get_run(self, run_id: str) -> RunRecord | None:
        return self._mem.get_run(run_id)
