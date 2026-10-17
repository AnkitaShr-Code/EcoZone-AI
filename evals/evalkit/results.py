"""Local JSONL rows (evals/RULES.md): `test, subject, result, value, run_at, commit, bundle_version` plus detail.

Outcome rows (`result` = pass, fail, xfail, xpass, skip) come from the pytest hook in conftest.py. Measure rows
(`result` = measured) carry a number or small object a test produced; they are what REPORT.md quotes.
"""

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .bundle import REPO_ROOT

RESULTS_DIR = REPO_ROOT / "evals" / "results"
ENV_RESULTS = "ECOZONE_EVAL_RESULTS"


def git_commit() -> tuple[str, bool]:
    """(full SHA, dirty). Dirty ignores the local results folder."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", ".", ":!evals/results"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return sha, bool(status)
    except (OSError, subprocess.CalledProcessError):
        return "unknown", True


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Recorder:
    path: Path
    commit: str
    dirty: bool
    bundle_version: str
    area_id: str

    @classmethod
    def create(cls, bundle_version: str, area_id: str) -> "Recorder":
        env = os.environ.get(ENV_RESULTS)
        if env:
            path = Path(env)
        else:
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            path = RESULTS_DIR / f"run-{stamp}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
        sha, dirty = git_commit()
        return cls(path, sha, dirty, bundle_version, area_id)

    def row(self, test: str, subject: str, result: str, value: Any = None, detail: str = "") -> None:
        row = {
            "test": test,
            "subject": subject,
            "result": result,
            "value": value,
            "detail": detail,
            "run_at": now(),
            "commit": self.commit,
            "dirty": self.dirty,
            "bundle_version": self.bundle_version,
            "area_id": self.area_id,
        }
        with self.path.open("a") as f:
            f.write(json.dumps(row, sort_keys=True, allow_nan=True) + "\n")

    def measure(self, test: str, subject: str, value: Any, detail: str = "") -> None:
        self.row(test, subject, "measured", value, detail)
