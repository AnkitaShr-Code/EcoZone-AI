"""Which bundle the evals run on, and its tune/test block split.

Order: `ECOZONE_EVAL_BUNDLE` (a path; an invalid path is an error, never a silent fallback), then the default
Deccan bundle (`data/areas/deccan/v1` in this checkout or in the main checkout when this is a worktree), then the
tiny fixture, so the suite always runs something and says which bundle it ran on.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
TINY = REPO_ROOT / "engine" / "tests" / "fixtures" / "tiny"
DEFAULT_REL = Path("data") / "areas" / "deccan" / "v1"
ENV_BUNDLE = "ECOZONE_EVAL_BUNDLE"

Kind = Literal["env", "default", "tiny"]


@dataclass(frozen=True)
class BundleChoice:
    path: Path
    kind: Kind
    note: str


@dataclass(frozen=True)
class BundleInfo:
    path: Path
    kind: Kind
    note: str
    meta: dict[str, Any]
    area_id: str
    bundle_version: str
    split: dict[str, str]
    """block id -> 'tune' or 'test'."""

    @property
    def tune_ids(self) -> list[str]:
        return sorted(b for b, s in self.split.items() if s == "tune")

    @property
    def test_ids(self) -> list[str]:
        return sorted(b for b, s in self.split.items() if s == "test")


def main_checkout() -> Path | None:
    """The main checkout's root when REPO_ROOT is a linked worktree (its `.git` is a file)."""
    dot_git = REPO_ROOT / ".git"
    if not dot_git.is_file():
        return None
    text = dot_git.read_text().strip()
    if not text.startswith("gitdir:"):
        return None
    gitdir = Path(text.split(":", 1)[1].strip())
    # <main>/.git/worktrees/<name>
    return gitdir.parents[1].parent if gitdir.parent.name == "worktrees" else None


def choose_bundle() -> BundleChoice:
    env = os.environ.get(ENV_BUNDLE)
    if env:
        path = Path(env).expanduser()
        if not (path / "meta.json").is_file():
            raise FileNotFoundError(f"{ENV_BUNDLE}={env} has no meta.json: not a bundle directory")
        return BundleChoice(path, "env", f"{ENV_BUNDLE}")
    roots = [REPO_ROOT, main_checkout()]
    for root in roots:
        if root is not None and (root / DEFAULT_REL / "meta.json").is_file():
            return BundleChoice(root / DEFAULT_REL, "default", f"default path {DEFAULT_REL}")
    return BundleChoice(
        TINY,
        "tiny",
        f"tiny fixture: no real bundle found (set {ENV_BUNDLE} or place one at {DEFAULT_REL}); "
        "numbers below are from the tiny fixture, not Deccan",
    )


def read_split(path: Path, meta: dict[str, Any]) -> dict[str, str]:
    """Block split from meta (`tune_blocks`, `test_blocks`) when present, else the blocks.parquet `split` column."""
    tune, test = meta.get("tune_blocks"), meta.get("test_blocks")
    if isinstance(tune, list) and isinstance(test, list):
        return {**{str(b): "tune" for b in tune}, **{str(b): "test" for b in test}}  # pyright: ignore[reportUnknownArgumentType]
    table = pq.read_table(path / "blocks.parquet", columns=["id", "split"]).to_pydict()
    return {str(i): str(s) for i, s in zip(table["id"], table["split"], strict=True)}


def describe(choice: BundleChoice) -> BundleInfo:
    meta: dict[str, Any] = json.loads((choice.path / "meta.json").read_text())
    return BundleInfo(
        path=choice.path,
        kind=choice.kind,
        note=choice.note,
        meta=meta,
        area_id=str(meta["area_id"]),
        bundle_version=str(meta["bundle_version"]),
        split=read_split(choice.path, meta),
    )
