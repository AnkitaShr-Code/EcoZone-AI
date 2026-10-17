"""Run the whole pipeline once on the tiny synthetic area; the step tests read its outputs."""

from __future__ import annotations

import pytest
from tiny_area import FIXTURES, Tiny, run_all

from ecozone_pipeline.config import Paths, load_config


@pytest.fixture(scope="session")
def tiny(tmp_path_factory: pytest.TempPathFactory) -> Tiny:
    root = tmp_path_factory.mktemp("tiny")
    cfg = load_config("tiny", FIXTURES / "tiny.yaml")
    paths = Paths.for_area(cfg.area_id, root)
    return Tiny(cfg, paths, run_all(cfg, paths, root / "bundle"))
