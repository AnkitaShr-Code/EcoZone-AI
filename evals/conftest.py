"""Session fixtures for the evals: which bundle, the workbench, the results recorder and the outcome rows."""

import os
import platform
from collections.abc import Iterator
from typing import Any

import pytest

from evalkit.bench import Bench
from evalkit.bundle import BundleInfo, choose_bundle, describe
from evalkit.cases import AreaCases, load_cases
from evalkit.results import Recorder

_STATE: dict[str, Any] = {}


def _info() -> BundleInfo:
    if "info" not in _STATE:
        _STATE["info"] = describe(choose_bundle())
    return _STATE["info"]


def _recorder() -> Recorder:
    if "rec" not in _STATE:
        info = _info()
        _STATE["rec"] = Recorder.create(info.bundle_version, info.area_id)
    return _STATE["rec"]


def pytest_report_header(config: pytest.Config) -> list[str]:
    info = _info()
    return [
        f"evals bundle: {info.area_id} {info.bundle_version} at {info.path} ({info.note})",
        f"evals blocks: {len(info.tune_ids)} tune, {len(info.test_ids)} test; results: {_recorder().path}",
    ]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Iterator[None]:
    outcome = yield
    rep: pytest.TestReport = outcome.get_result()
    if rep.when == "call" or (rep.when == "setup" and rep.outcome != "passed"):
        result = rep.outcome
        if hasattr(rep, "wasxfail"):
            result = "xfail" if rep.skipped else "xpass"
        elif rep.skipped:
            result = "skip"
        detail = ""
        if rep.failed and call.excinfo is not None:
            detail = str(call.excinfo.value)[:1500]
        elif rep.skipped or hasattr(rep, "wasxfail"):
            detail = str(getattr(rep, "wasxfail", "") or (rep.longrepr[2] if isinstance(rep.longrepr, tuple) else ""))
        _recorder().row(item.nodeid, "outcome", result, rep.duration, detail)


@pytest.fixture(scope="session")
def info() -> BundleInfo:
    return _info()


@pytest.fixture(scope="session")
def rec() -> Recorder:
    return _recorder()


@pytest.fixture(scope="session", autouse=True)
def _record_session(info: BundleInfo, rec: Recorder) -> None:
    m = info.meta
    rec.measure(
        "session",
        "bundle",
        {
            "area_id": info.area_id,
            "bundle_version": info.bundle_version,
            "bundle_kind": info.kind,
            "bundle_note": info.note,
            "name": m.get("name"),
            "reference_date": m.get("reference_date"),
            "pipeline_git_sha": m.get("pipeline_git_sha"),
            "settings_hash": m.get("settings_hash"),
            "counts": m.get("counts"),
            "skipped_steps": m.get("skipped_steps"),
            "tune_blocks": len(info.tune_ids),
            "test_blocks": len(info.test_ids),
        },
    )
    rec.measure(
        "session",
        "machine",
        {"platform": platform.platform(), "cpus": os.cpu_count(), "python": platform.python_version()},
    )


@pytest.fixture(scope="session")
def cases(info: BundleInfo) -> AreaCases:
    cs = load_cases(info.area_id)
    assert cs.bundle_version == info.bundle_version, (
        f"cases.yaml was written for {info.area_id} {cs.bundle_version}, bundle is {info.bundle_version}"
    )
    return cs


@pytest.fixture(scope="session")
def bench(info: BundleInfo, cases: AreaCases, rec: Recorder) -> Bench:
    b = Bench.create(info, cases)
    rec.measure("session", "bundle_load", b.load_seconds, "seconds, load_bundle")
    return b
