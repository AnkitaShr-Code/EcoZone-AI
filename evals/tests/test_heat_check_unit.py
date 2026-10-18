"""The heat-check statistics, the table join, the eval test itself on a synthetic table, and the report section."""

import itertools
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import report
from evalkit import heat_check as hc
from evalkit.bundle import REPO_ROOT, TINY

# ---------- statistics ----------


def test_average_ranks_share_the_mean_rank_of_ties() -> None:
    assert hc.average_ranks([10.0, 20.0, 20.0, 5.0]).tolist() == [2.0, 3.5, 3.5, 1.0]
    assert hc.average_ranks([3.0, 3.0, 3.0]).tolist() == [2.0, 2.0, 2.0]


def test_spearman_known_values() -> None:
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert hc.spearman(x, [10.0, 20.0, 35.0, 90.0, 91.0]) == pytest.approx(1.0)  # any increasing relation
    assert hc.spearman(x, [9.0, 7.0, 5.0, 3.0, 1.0]) == pytest.approx(-1.0)
    # ties on one side: ranks [1,2,3,4] and [1.5,1.5,3.5,3.5] -> 4 / sqrt(5 * 4)
    assert hc.spearman([1.0, 2.0, 3.0, 4.0], [1.0, 1.0, 2.0, 2.0]) == pytest.approx(4 / math.sqrt(20))
    assert math.isnan(hc.spearman(x, [2.0] * 5))


def test_spearman_is_symmetric_and_rank_based() -> None:
    rng = np.random.default_rng(1)
    a, b = rng.normal(size=30), rng.normal(size=30)
    assert hc.spearman(a, b) == pytest.approx(hc.spearman(b, a))
    assert hc.spearman(a, b) == pytest.approx(hc.spearman(np.exp(a), b**3))


def exact_p(x: list[float], y: list[float]) -> float:
    observed = abs(hc.spearman(x, y))
    rhos = [abs(hc.spearman(x, list(p))) for p in itertools.permutations(y)]
    return sum(r >= observed - 1e-12 for r in rhos) / len(rhos)


def test_permutation_p_matches_the_exact_value_on_a_small_case() -> None:
    x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    y = [2.0, 1.0, 4.0, 3.0, 7.0, 5.0, 6.0]
    assert hc.permutation_p(x, y) == pytest.approx(exact_p(x, y), abs=0.02)


def test_permutation_p_extremes_and_determinism() -> None:
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert hc.permutation_p(x, x) == pytest.approx(2 / 120, abs=0.006)  # only the two monotone pairings reach |rho| = 1
    assert hc.permutation_p(x, x) == hc.permutation_p(x, x)  # fixed seed
    assert hc.permutation_p(x, [3.0, 1.0, 5.0, 2.0, 4.0]) > 0.5
    assert math.isnan(hc.permutation_p(x, [1.0] * 5))


# ---------- the join ----------


def baselines(n: int) -> dict[str, SimpleNamespace]:
    return {f"blk_{i}": SimpleNamespace(vci=i % 7, hei=float(i), gcs=100 - i, pss=(i * 3) % 11) for i in range(n)}


def test_join_and_correlations_by_split() -> None:
    b = baselines(12)
    split = {k: ("test" if i % 2 else "tune") for i, k in enumerate(b)}
    lst = pd.DataFrame(
        {"block_id": list(b), "lst_kelvin": [300.0 + 2 * i for i in range(12)], "valid_pixels": [5] * 12}
    )
    frame = hc.join_blocks(lst, b, split)
    cors = hc.correlations(frame, "hei")
    assert (cors["test"].n, cors["tune"].n, cors["all"].n) == (6, 6, 12)
    assert all(c.rho == pytest.approx(1.0) for c in cors.values())
    assert hc.correlations(frame, "gcs")["all"].rho == pytest.approx(-1.0)


def test_join_rejects_blocks_the_bundle_does_not_have() -> None:
    lst = pd.DataFrame({"block_id": ["blk_0", "blk_99"], "lst_kelvin": [300.0, 301.0], "valid_pixels": [4, 4]})
    with pytest.raises(ValueError, match="not in the bundle"):
        hc.join_blocks(lst, baselines(2), {"blk_0": "test", "blk_1": "tune"})


def test_not_run_message_names_the_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(hc.ENV_DATA_DIR, raising=False)
    msg = hc.not_run_message("deccan")
    assert msg.startswith("heat check: not run")
    assert "pipeline heat-check --area deccan" in msg
    assert "evals/heat_check/data/deccan_block_lst.csv" in msg


# ---------- the eval test itself, on the tiny bundle with a synthetic table ----------

TINY_IDS = [f"blk_000{i}" for i in range(1, 7)]


def write_synthetic(folder: Path, **meta_override: object) -> None:
    pd.DataFrame(
        {
            "block_id": TINY_IDS,
            "lst_kelvin": [301.0, 303.5, 299.2, 305.1, 302.2, 300.4],
            "valid_pixels": [9, 12, 7, 20, 15, 11],
        }
    ).to_csv(folder / "tiny_block_lst.csv", index=False)
    meta = {
        "datasets": ["LANDSAT/LC08/C02/T1_L2", "LANDSAT/LC09/C02/T1_L2"],
        "windows": [{"year": 2026, "start": "2026-03-01", "end": "2026-05-31", "scenes": {"a": 3, "b": 4}}],
        "years_used": [2026],
        "scenes_total": 7,
        "min_scenes": 5,
        "min_scenes_met": True,
        "fetch_date": "2026-10-18",
        "earth_engine_project": "synthetic",
        "scale_m": 30,
        "native_thermal_resolution_m": 100,
        "scene_max_cloud_cover_pct": 30.0,
        "st_qa_max_uncertainty_k": 5.0,
        "blocks_requested": 6,
        "blocks_with_lst": 6,
        "blocks_dropped": [],
        "valid_pixels_min": 7,
        "valid_pixels_median": 12,
        "valid_pixels_max": 20,
        "bundle_version": "v1",
        "bundle_settings_hash": "x",
    }
    meta.update(meta_override)
    (folder / "tiny_block_lst.meta.json").write_text(json.dumps(meta))


def run_eval(data: Path, results: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "ECOZONE_EVAL_BUNDLE": str(TINY),
        hc.ENV_DATA_DIR: str(data),
        "ECOZONE_EVAL_RESULTS": str(results),
    }
    return subprocess.run(
        [sys.executable, "-m", "pytest", "evals/test_heat_check.py", "-rs", "-p", "no:cacheprovider"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def rows_of(path: Path) -> list[report.Row]:
    return report.read_rows(path)


@pytest.fixture(scope="module")
def missing_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[subprocess.CompletedProcess[str], Path]:
    folder = tmp_path_factory.mktemp("missing")
    return run_eval(folder, folder / "rows.jsonl"), folder / "rows.jsonl"


@pytest.fixture(scope="module")
def synthetic_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[subprocess.CompletedProcess[str], Path]:
    folder = tmp_path_factory.mktemp("synthetic")
    write_synthetic(folder)
    return run_eval(folder, folder / "rows.jsonl"), folder / "rows.jsonl"


def test_eval_skips_with_the_command_when_the_table_is_missing(
    missing_run: tuple[subprocess.CompletedProcess[str], Path],
) -> None:
    done, rows_file = missing_run
    assert done.returncode == 0, done.stdout + done.stderr
    assert "heat check: not run" in done.stdout
    assert "pipeline heat-check --area tiny" in done.stdout
    rows = rows_of(rows_file)
    assert [r["result"] for r in rows if r["subject"] == "outcome"] == ["skip"]
    assert not [r for r in rows if r["test"].startswith("heat_check")]


def test_eval_reports_test_all_and_tune_with_provenance(
    synthetic_run: tuple[subprocess.CompletedProcess[str], Path],
) -> None:
    done, rows_file = synthetic_run
    assert done.returncode == 0, done.stdout + done.stderr
    rows = rows_of(rows_file)
    primary = {r["subject"]: r["value"] for r in rows if r["test"] == "heat_check.primary"}
    assert set(primary) == {"hei:test", "hei:all", "hei:tune"}
    assert (primary["hei:test"]["n"], primary["hei:tune"]["n"], primary["hei:all"]["n"]) == (3, 3, 6)
    for v in primary.values():
        assert -1 <= v["rho"] <= 1
        assert 0 < v["p_value"] <= 1
        assert (v["permutations"], v["seed"]) == (10_000, hc.SEED)
    secondary = {r["subject"] for r in rows if r["test"] == "heat_check.secondary"}
    assert secondary == {f"{i}:{s}" for i in hc.SECONDARY for s in ("test", "all", "tune")}
    (prov,) = (r["value"] for r in rows if r["test"] == "heat_check.provenance")
    assert prov["scenes_total"] == 7
    assert prov["bundle_version_matches"] is True
    assert prov["bundle_settings_hash_matches"] is False  # the synthetic sidecar carries a made-up hash
    assert "lst_kelvin" not in json.dumps(rows)  # no temperatures in the rows


def test_eval_fails_on_a_malformed_table(tmp_path: Path) -> None:
    write_synthetic(tmp_path)
    frame = pd.read_csv(tmp_path / "tiny_block_lst.csv")
    frame.loc[0, "block_id"] = "blk_9999"  # not a block of the bundle
    frame.to_csv(tmp_path / "tiny_block_lst.csv", index=False)
    done = run_eval(tmp_path, tmp_path / "rows.jsonl")
    assert done.returncode != 0
    assert "not in the bundle" in done.stdout


# ---------- the report section ----------

CAVEATS = (
    "not the air temperature",
    "shares inputs",
    "top of a shade structure",
    "100 m",
    "small sample",
)


def test_report_has_a_heat_check_section_with_numbers_caveats_and_no_temperatures(
    synthetic_run: tuple[subprocess.CompletedProcess[str], Path],
) -> None:
    text = report.build(rows_of(synthetic_run[1]))
    section = text.split("## Heat check", 1)[1].split("\n## ", 1)[0]
    assert "not run" not in section.lower()
    assert "LANDSAT/LC08/C02/T1_L2" in section and "LANDSAT/LC09/C02/T1_L2" in section
    assert "2026-03-01" in section and "2026-05-31" in section
    assert "7 scenes" in section
    for phrase in CAVEATS:
        assert phrase in section
    assert re.search(r"\| HEI \| test \(held out, headline\) \| 3 of 3 \| [-+]\d\.\d{3} \| [01]\.\d{4} \|", section), (
        section
    )
    assert "°" not in text and "celsius" not in text.lower() and "kelvin" not in section.lower()
    assert "heat check" not in text.split("## Not run", 1)[1].lower()


def test_report_says_heat_check_not_run_without_data(
    missing_run: tuple[subprocess.CompletedProcess[str], Path],
) -> None:
    text = report.build(rows_of(missing_run[1]))
    section = text.split("## Heat check", 1)[1].split("\n## ", 1)[0]
    assert "heat check: not run" in section.lower()
    assert "pipeline heat-check --area" in section
    assert "No correlation is reported" in section
