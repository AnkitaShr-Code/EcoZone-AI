"""The Earth Engine heat-check step, offline: a numpy fake of `ee` (fake_ee.py) and a fake backend. No network."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from fake_ee import FakeEe, Scene
from shapely.geometry import box, mapping
from tiny_area import FIXTURES, Tiny
from typer.testing import CliRunner

from ecozone_pipeline import cli
from ecozone_pipeline.steps import earth_engine as ee_step
from ecozone_pipeline.steps.earth_engine import (
    DEFAULT_PROJECT,
    ENV_PROJECT,
    ENV_TOKEN,
    BlockPolygon,
    BlockReduction,
    DateWindow,
    EarthEngineError,
    EeBackend,
    HeatCheckError,
    LstSettings,
    NoScenesError,
    fetch_block_lst,
    initialize,
    season_window,
)

L8 = "LANDSAT/LC08/C02/T1_L2"
CLEAR = 1 << 6  # QA_PIXEL with only the "clear" bit set
L9 = "LANDSAT/LC09/C02/T1_L2"

# Four pixel centres, one per quadrant of the unit square; block A covers the first two, block B the other two.
XY = np.array([[0.25, 0.25], [0.75, 0.25], [0.25, 0.75], [0.75, 0.75]])
A = BlockPolygon("blk_a", mapping(box(0.0, 0.0, 1.0, 0.5)))
B = BlockPolygon("blk_b", mapping(box(0.0, 0.5, 1.0, 1.0)))
SETTINGS = LstSettings()
WIN_2026 = season_window(2026, SETTINGS)


def scene(
    day: str,
    dn: float | list[float] = 40000,
    qa: int | list[int] = CLEAR,
    unc: int | list[int] = 200,
    cloud: float = 5.0,
    dataset: str = L8,
) -> Scene:
    def px(v: float | list[float]) -> np.ndarray:
        return np.broadcast_to(np.asarray(v, dtype=float), (len(XY),)).copy()

    return Scene(dataset, day, {"CLOUD_COVER": cloud}, {"ST_B10": px(dn), "QA_PIXEL": px(qa), "ST_QA": px(unc)})


def backend(scenes: list[Scene]) -> tuple[EeBackend, FakeEe]:
    fake = FakeEe(XY, scenes)
    return EeBackend(fake, SETTINGS, (0.0, 0.0, 1.0, 1.0), "proj"), fake


def reduce_one(scenes: list[Scene], blocks: list[BlockPolygon] | None = None) -> dict[str, BlockReduction]:
    be, _ = backend(scenes)
    return {r.block_id: r for r in be.reduce_blocks(blocks or [A, B], [WIN_2026])}


# ---------- scale factor and offset ----------


def test_scale_factor_and_offset() -> None:
    # 40000 x 0.00341802 + 149.0 = 285.7208 K, computed by hand.
    r = reduce_one([scene("2026-04-10", dn=40000)])
    assert r["blk_a"].median_kelvin == pytest.approx(285.7208, abs=1e-9)
    assert r["blk_a"].pixel_count == 2
    # Smallest and largest valid counts map to the documented range.
    low = reduce_one([scene("2026-04-10", dn=1)])["blk_a"].median_kelvin
    high = reduce_one([scene("2026-04-10", dn=65535)])["blk_a"].median_kelvin
    assert low == pytest.approx(149.00341802, abs=1e-9)
    assert high == pytest.approx(65535 * 0.00341802 + 149.0, abs=1e-9)


def test_reduction_uses_30m_in_the_bundle_crs() -> None:
    be, fake = backend([scene("2026-04-10")])
    be.reduce_blocks([A], [WIN_2026])
    assert ("filterDate", ("2026-03-01", "2026-06-01")) in fake.calls  # May 31 inclusive: end is exclusive


# ---------- QA_PIXEL bits ----------


@pytest.mark.parametrize("bit", [1, 2, 3, 4])
def test_cloud_bits_are_masked(bit: int) -> None:
    # dilated cloud, cirrus, cloud, cloud shadow: pixel 0 flagged, pixel 1 clear -> block A keeps one pixel.
    r = reduce_one([scene("2026-04-10", qa=[CLEAR | (1 << bit), CLEAR, CLEAR, CLEAR])])
    assert r["blk_a"].pixel_count == 1
    assert r["blk_b"].pixel_count == 2


@pytest.mark.parametrize("bit", [0, 5, 6, 7])
def test_other_bits_are_not_cloud_masks(bit: int) -> None:
    # fill is dropped by the ST_B10 = 0 rule, snow and water are real surfaces, clear is the good case
    r = reduce_one([scene("2026-04-10", qa=1 << bit)])
    assert r["blk_a"].pixel_count == 2


def test_fill_value_in_the_thermal_band_is_masked() -> None:
    r = reduce_one([scene("2026-04-10", dn=[0, 40000, 40000, 40000])])
    assert r["blk_a"].pixel_count == 1
    assert r["blk_a"].median_kelvin == pytest.approx(285.7208)


# ---------- ST_QA uncertainty ----------


@pytest.mark.parametrize(("unc", "kept"), [(0, True), (500, True), (501, False), (3000, False), (-9999, False)])
def test_st_qa_threshold(unc: int, kept: bool) -> None:
    # 500 counts x 0.01 K = 5.0 K is the limit and is kept; -9999 is the fill value
    r = reduce_one([scene("2026-04-10", unc=[unc, unc, unc, unc])])
    assert (r["blk_a"].pixel_count == 2) is kept
    assert (r["blk_a"].median_kelvin is not None) is kept


def test_threshold_follows_the_setting() -> None:
    be = EeBackend(FakeEe(XY, [scene("2026-04-10", unc=250)]), LstSettings(max_st_uncertainty_k=2.0), (0, 0, 1, 1), "p")
    assert be.reduce_blocks([A], [WIN_2026])[0].pixel_count == 0


# ---------- composite ----------


def test_median_ignores_masked_values_and_other_dates() -> None:
    scenes = [
        scene("2026-03-05", dn=30000),
        scene("2026-04-10", dn=40000),
        scene("2026-05-31", dn=50000),  # last day of the window is inside
        scene("2026-04-20", dn=60000, qa=1 << 3),  # cloudy: must not pull the median up
        scene("2026-02-28", dn=65000),  # before the window
        scene("2026-06-01", dn=65000),  # after the window
        scene("2026-04-12", dn=65000, cloud=60.0),  # scene-level cloud cover over the limit
    ]
    r = reduce_one(scenes)["blk_a"]
    assert r.median_kelvin == pytest.approx(40000 * 0.00341802 + 149.0)


def test_both_landsats_and_both_windows_are_merged() -> None:
    scenes = [
        scene("2026-04-10", dn=30000, dataset=L8),
        scene("2026-04-11", dn=40000, dataset=L9),
        scene("2025-04-10", dn=50000, dataset=L8),
    ]
    be, _ = backend(scenes)
    one = be.reduce_blocks([A], [season_window(2026, SETTINGS)])[0]
    both = be.reduce_blocks([A], [season_window(2026, SETTINGS), season_window(2025, SETTINGS)])[0]
    assert one.median_kelvin == pytest.approx(35000 * 0.00341802 + 149.0)
    assert both.median_kelvin == pytest.approx(40000 * 0.00341802 + 149.0)


def test_block_without_valid_pixels_has_no_median() -> None:
    r = reduce_one([scene("2026-04-10", qa=[1 << 3, 1 << 3, CLEAR, CLEAR])])
    assert r["blk_a"].median_kelvin is None
    assert r["blk_a"].pixel_count == 0
    assert r["blk_b"].pixel_count == 2


# ---------- the step: dropping, fallback, provenance ----------


class StubBackend:
    def __init__(self, counts: dict[tuple[int, str], int], reductions: list[BlockReduction]) -> None:
        self.counts = counts
        self.reductions = reductions
        self.asked: list[int] = []
        self.windows: list[DateWindow] = []

    def scene_count(self, dataset_id: str, window: DateWindow) -> int:
        self.asked.append(window.year)
        return self.counts.get((window.year, dataset_id), 0)

    def reduce_blocks(self, blocks: Any, windows: Any) -> list[BlockReduction]:
        self.windows = list(windows)
        return self.reductions

    def info(self) -> dict[str, str]:
        return {"project": "proj-x", "earthengine_api_version": "9.9"}


def run_fetch(be: StubBackend, blocks: list[str]) -> ee_step.LstResult:
    polys = [BlockPolygon(b, {}) for b in blocks]
    return fetch_block_lst(polys, be, SETTINGS, 2026, date(2026, 10, 18), {"area_id": "deccan", "bundle_version": "v1"})


def test_blocks_without_pixels_are_dropped_and_listed() -> None:
    red = [
        BlockReduction("blk_a", 301.5, 12.0),
        BlockReduction("blk_b", None, 0.0),
        BlockReduction("blk_c", 300.0, 0.0),  # a median with no coverage behind it
        BlockReduction("blk_d", float("nan"), 3.0),
        BlockReduction("blk_unknown", 300.0, 9.0),  # not asked for
    ]
    res = run_fetch(StubBackend({(2026, L8): 6}, red), ["blk_a", "blk_b", "blk_c", "blk_d", "blk_e"])
    assert list(res.table["block_id"]) == ["blk_a"]
    assert list(res.table.columns) == ["block_id", "lst_kelvin", "valid_pixels"]
    assert res.table["valid_pixels"].tolist() == [12.0]
    assert res.meta["blocks_requested"] == 5
    assert res.meta["blocks_with_lst"] == 1
    assert res.meta["blocks_dropped"] == ["blk_b", "blk_c", "blk_d", "blk_e"]  # blk_e was never returned


def test_partly_covered_pixels_still_count_as_valid() -> None:
    res = run_fetch(StubBackend({(2026, L8): 6}, [BlockReduction("blk_a", 301.5, 0.456)]), ["blk_a"])
    assert res.table["valid_pixels"].tolist() == [0.46]
    assert res.meta["blocks_dropped"] == []


def test_enough_scenes_in_the_reference_year_do_not_pull_in_the_year_before() -> None:
    be = StubBackend({(2026, L8): 3, (2026, L9): 2, (2025, L8): 9}, [BlockReduction("blk_a", 300.0, 4.0)])
    res = run_fetch(be, ["blk_a"])
    assert res.meta["years_used"] == [2026]
    assert res.meta["fallback_year_used"] is False
    assert res.meta["scenes_total"] == 5
    assert res.meta["min_scenes_met"] is True
    assert set(be.asked) == {2026}
    assert [w.year for w in be.windows] == [2026]


def test_too_few_scenes_adds_the_year_before() -> None:
    be = StubBackend(
        {(2026, L8): 2, (2026, L9): 1, (2025, L8): 4, (2025, L9): 3}, [BlockReduction("blk_a", 300.0, 4.0)]
    )
    res = run_fetch(be, ["blk_a"])
    assert res.meta["years_used"] == [2026, 2025]
    assert res.meta["fallback_year_used"] is True
    assert res.meta["scenes_total"] == 10
    assert [w.year for w in be.windows] == [2026, 2025]
    assert res.meta["windows"][1]["scenes"] == {L8: 4, L9: 3}


def test_still_too_few_scenes_is_recorded_not_hidden() -> None:
    be = StubBackend({(2026, L8): 1, (2025, L9): 1}, [BlockReduction("blk_a", 300.0, 4.0)])
    res = run_fetch(be, ["blk_a"])
    assert res.meta["years_used"] == [2026, 2025]
    assert res.meta["scenes_total"] == 2
    assert res.meta["min_scenes_met"] is False


def test_no_scenes_at_all_is_an_error() -> None:
    with pytest.raises(NoScenesError, match="2026-03-01"):
        run_fetch(StubBackend({}, []), ["blk_a"])


def test_provenance_is_recorded_and_holds_no_temperature() -> None:
    res = run_fetch(StubBackend({(2026, L8): 6}, [BlockReduction("blk_a", 301.5, 12.0)]), ["blk_a"])
    m = res.meta
    assert m["datasets"] == [L8, L9]
    assert m["band"] == "ST_B10"
    assert (m["scale_factor"], m["offset"]) == (0.00341802, 149.0)
    assert m["windows"][0]["start"] == "2026-03-01"
    assert m["windows"][0]["end"] == "2026-05-31"
    assert m["fetch_date"] == "2026-10-18"
    assert m["earth_engine_project"] == "proj-x"
    assert m["qa_pixel_masked"]["mask"] == 0b11110
    assert m["st_qa_max_uncertainty_k"] == 5.0
    assert m["bundle_version"] == "v1"
    assert "301.5" not in json.dumps(m)


def test_season_window_edges() -> None:
    w = season_window(2025, SETTINGS)
    assert (w.start, w.end) == (date(2025, 3, 1), date(2025, 5, 31))
    assert w.end_exclusive == date(2025, 6, 1)


# ---------- the step on the tiny bundle ----------


def test_run_writes_csv_and_meta_from_the_bundle(tiny: Tiny, tmp_path: Path) -> None:
    blocks = tiny.bundle_table("blocks")
    ids = sorted(str(i) for i in blocks["id"])
    red = [BlockReduction(b, 300.0 + i, 10.0 + i) for i, b in enumerate(ids[:-1])]  # the last block gets nothing
    stub = StubBackend({(2026, L8): 8}, red)
    csv = tmp_path / "out" / "tiny_block_lst.csv"
    summary = ee_step.run(tiny.cfg, tiny.paths, csv, backend=stub, bundle_dir=tiny.bundle_dir, today=date(2026, 10, 18))
    table = pd.read_csv(csv)
    assert list(table.columns) == ["block_id", "lst_kelvin", "valid_pixels"]
    assert table["block_id"].tolist() == ids[:-1]
    meta = json.loads(csv.with_suffix(".meta.json").read_text())
    assert csv.with_suffix(".meta.json").name == "tiny_block_lst.meta.json"
    assert meta["blocks_dropped"] == [ids[-1]]
    assert meta["area_id"] == "tiny"
    assert summary["blocks_with_lst"] == len(ids) - 1


def test_block_polygons_are_wgs84(tiny: Tiny) -> None:
    polys = ee_step.block_polygons(tiny.bundle_table("blocks"))
    w, s, e, n = tiny.cfg.bbox_wgs84
    assert polys
    for p in polys:
        for lon, lat in np.asarray(p.geometry["coordinates"][0]):
            assert w - 0.01 < lon < e + 0.01
            assert s - 0.01 < lat < n + 0.01
    assert [p.block_id for p in polys] == sorted(p.block_id for p in polys)


def test_missing_bundle_is_a_clear_error(tiny: Tiny, tmp_path: Path) -> None:
    with pytest.raises(HeatCheckError, match="Build the bundle first"):
        ee_step.run(tiny.cfg, tiny.paths, tmp_path / "x.csv", backend=StubBackend({}, []), bundle_dir=tmp_path / "none")


# ---------- authentication ----------


def test_project_defaults_and_no_token() -> None:
    fake = FakeEe(XY, [])
    assert initialize(fake, {}) == DEFAULT_PROJECT == "ecozone-ai-2026"
    assert fake.initialize_kwargs == [{"project": "ecozone-ai-2026"}]


def test_project_from_env() -> None:
    fake = FakeEe(XY, [])
    assert initialize(fake, {ENV_PROJECT: "my-proj"}) == "my-proj"
    assert fake.initialize_kwargs == [{"project": "my-proj"}]


def test_access_token_builds_oauth_credentials() -> None:
    fake = FakeEe(XY, [])
    initialize(fake, {ENV_TOKEN: "ya29.test-token", ENV_PROJECT: "p1"})
    (kwargs,) = fake.initialize_kwargs
    creds = kwargs["credentials"]
    assert kwargs["project"] == "p1"
    assert creds.token == "ya29.test-token"
    assert set(creds.scopes) == {
        "https://www.googleapis.com/auth/earthengine",
        "https://www.googleapis.com/auth/cloud-platform",
    }


def test_initialisation_failure_names_the_fix_and_hides_the_token() -> None:
    fake = FakeEe(XY, [])
    fake.fail_initialize = RuntimeError("permission denied")
    with pytest.raises(EarthEngineError) as err:
        initialize(fake, {ENV_TOKEN: "ya29.secret"})
    assert "roles/earthengine.viewer" in str(err.value)
    assert "ya29.secret" not in str(err.value)


# ---------- ee stays optional ----------

HIDE_EE = "import sys; sys.modules['ee'] = None\n"  # `import ee` now raises ImportError


def run_python(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-c", HIDE_EE + code], capture_output=True, text=True, check=False)


def test_importing_the_pipeline_never_imports_ee() -> None:
    code = (
        "import ecozone_pipeline, ecozone_pipeline.cli, ecozone_pipeline.steps.earth_engine\n"
        "from ecozone_pipeline.cli import app\n"
        "assert [m for m in sys.modules if m == 'ee' and sys.modules[m] is not None] == []\n"
    )
    done = run_python(code)
    assert done.returncode == 0, done.stderr


def test_missing_client_gives_a_clear_message() -> None:
    done = run_python(
        "from ecozone_pipeline.steps.earth_engine import load_ee, EarthEngineError\n"
        "try:\n    load_ee()\nexcept EarthEngineError as e:\n    print(e)\n"
    )
    assert done.returncode == 0, done.stderr
    assert "--extra ee" in done.stdout


# ---------- the command ----------


def test_heat_check_is_not_part_of_all() -> None:
    assert "heat-check" not in cli.STEPS
    assert "earth_engine" not in {name for name in cli.STEPS}


def test_command_fails_clearly_without_earth_engine(
    tiny: Tiny, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_a: Any, **_k: Any) -> Any:
        raise EarthEngineError("Earth Engine could not be initialised")

    monkeypatch.setattr(ee_step, "connect", refuse)
    result = CliRunner().invoke(
        cli.app,
        [
            "heat-check", "--area", "tiny", "--config", str(FIXTURES / "tiny.yaml"), "--out", str(tiny.bundle_dir),
            "--heat-csv", str(tmp_path / "o.csv"),
        ],
    )  # fmt: skip
    assert result.exit_code == 1
    assert "could not be initialised" in result.output
    assert not (tmp_path / "o.csv").exists()


def test_command_writes_the_table(tiny: Tiny, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ids = sorted(str(i) for i in tiny.bundle_table("blocks")["id"])
    stub = StubBackend({(2026, L8): 9}, [BlockReduction(b, 299.0, 7.0) for b in ids])
    monkeypatch.setattr(ee_step, "connect", lambda *_a, **_k: stub)
    out = tmp_path / "o.csv"
    result = CliRunner().invoke(
        cli.app,
        [
            "heat-check", "--area", "tiny", "--config", str(FIXTURES / "tiny.yaml"), "--out", str(tiny.bundle_dir),
            "--heat-csv", str(out),
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert len(pd.read_csv(out)) == len(ids)
    assert "heat-check" in result.output
