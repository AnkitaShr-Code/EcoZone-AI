from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pytest
import shapely
from shapely import Point
from tiny_area import FIXTURES, Tiny
from typer.testing import CliRunner

from ecozone_engine import AreaScores, BaselineData, Scores
from ecozone_pipeline.cli import app
from ecozone_pipeline.steps import baselines
from ecozone_pipeline.steps.bundle import SCHEMA, load_tables, validate_tables


def meta(tiny: Tiny) -> dict[str, Any]:
    return json.loads((tiny.bundle_dir / "meta.json").read_text())


def test_bundle_has_every_table_and_meta(tiny: Tiny) -> None:
    names = {p.name for p in tiny.bundle_dir.iterdir()}
    assert names == {f"{t}.parquet" for t in SCHEMA} | {"meta.json"}


def test_bundle_passes_the_schema_check(tiny: Tiny) -> None:
    assert validate_tables(load_tables(tiny.bundle_dir), tiny.cfg.crs) == []


def test_bundle_geometry_is_utm_and_valid(tiny: Tiny) -> None:
    for name, gdf in load_tables(tiny.bundle_dir).items():
        assert gdf.crs is not None
        assert gdf.crs.to_epsg() == 32643, name
        assert gdf.geometry.is_valid.all(), name
        assert not gdf.geometry.is_empty.any(), name


def test_meta_records_provenance(tiny: Tiny) -> None:
    m = meta(tiny)
    assert m["schema_version"] == 1
    assert m["area_id"] == "tiny"
    assert m["bundle_version"] == "v1"
    assert m["crs"] == "EPSG:32643"
    assert len(m["sun"]) == 3
    assert m["wind_from_deg"] == 300.0
    assert m["V_ref"] > 0
    assert m["settings_hash"] == tiny.cfg.settings_hash
    assert m["pipeline_git_sha"]
    assert "ODbL" in m["attribution"]
    assert {s["name"].split(" ")[0] for s in m["sources"]} == {"OpenStreetMap", "Open-Meteo", "pvlib"}
    assert all(s["licence"] for s in m["sources"])


def test_meta_counts_match_the_tables(tiny: Tiny) -> None:
    m = meta(tiny)
    tables = load_tables(tiny.bundle_dir)
    assert m["counts"] == {
        "blocks": len(tables["blocks"]),
        "buildings": len(tables["buildings"]),
        "segments": len(tables["chunks"]),
        "wait_points": len(tables["wait_points"]),
        "sites": len(tables["sites"]),
        "parcels": len(tables["parcels"]),
    }
    assert sum(m["buildings_by_height_source"].values()) == len(tables["buildings"])
    assert m["derived_footpath_chunks"] == int((tables["chunks"]["footpath_source"] == "derived").sum())


def test_every_fallback_is_counted(tiny: Tiny) -> None:
    gaps = meta(tiny)["data_gaps"]
    assert gaps["buildings_height_from_typology"] == 15
    assert gaps["footpath_chunks_derived_from_road_edge"] > 0
    assert gaps["chunks_width_from_road_class"] == gaps["chunks_total"]
    assert gaps["roof_albedo_default_buildings"] == gaps["buildings_total"]


def test_optional_steps_declare_themselves(tiny: Tiny) -> None:
    assert "earth_engine" in meta(tiny)["skipped_steps"]


def test_rebuilding_gives_the_same_bundle(tiny: Tiny, tmp_path: Path) -> None:
    from ecozone_pipeline.steps import bundle

    again = bundle.run(tiny.cfg, tiny.paths, out_dir=tmp_path / "again")
    assert (again / "meta.json").read_text() == (tiny.bundle_dir / "meta.json").read_text()
    for name in SCHEMA:
        a, b = gpd.read_parquet(again / f"{name}.parquet"), gpd.read_parquet(tiny.bundle_dir / f"{name}.parquet")
        assert a.equals(b), name


def test_validation_catches_each_kind_of_problem(tiny: Tiny) -> None:
    def broken(**changes: Any) -> list[str]:
        tables = load_tables(tiny.bundle_dir)
        for name, fn in changes.items():
            tables[name] = fn(tables[name].copy())
        return validate_tables(tables, tiny.cfg.crs)

    assert any("column missing" in e for e in broken(blocks=lambda g: g.drop(columns=["I_s"])))
    assert any("duplicate ids" in e for e in broken(sites=lambda g: g.assign(id="s_0001")))
    assert any("ids must start" in e for e in broken(sites=lambda g: g.assign(id=[f"x{i}" for i in range(len(g))])))
    assert any("empty or missing" in e for e in broken(parcels=lambda g: g.set_geometry([Point()] * len(g))))
    assert any("unexpected values" in e for e in broken(blocks=lambda g: g.assign(split="train")))
    assert any("unknown blocks" in e for e in broken(chunks=lambda g: g.assign(block_id="blk_9999")))
    assert any("missing values" in e for e in broken(blocks=lambda g: g.assign(I_s=float("nan"))))
    assert any("infinite" in e for e in broken(blocks=lambda g: g.assign(I_s=float("inf"))))
    assert any("CRS" in e for e in broken(blocks=lambda g: g.set_crs(4326, allow_override=True)))


def test_baselines_are_skipped_until_the_engine_can_compute_them(tiny: Tiny, tmp_path: Path) -> None:
    out = tmp_path / "skip"
    out.mkdir()
    (out / "meta.json").write_text(json.dumps({"skipped_steps": ["earth_engine"]}))
    result = baselines.run(out)
    assert result["skipped"] == "baselines"
    assert json.loads((out / "meta.json").read_text())["skipped_steps"] == ["earth_engine", "baselines"]
    assert not (out / "baselines.parquet").exists()


def test_baselines_are_written_when_the_engine_provides_them(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = BaselineData(
        blocks=(("blk_0002", Scores(1, 2, 3, 4)), ("blk_0001", Scores(5, 6, 7, 8))),
        area=AreaScores(vci=3, hei=4, gcs=5, pss=6, acs=7),
    )
    monkeypatch.setattr(baselines, "load_bundle", lambda _p: object())
    monkeypatch.setattr(baselines, "compute_baselines", lambda _a: data)
    (tmp_path / "meta.json").write_text(json.dumps({"skipped_steps": ["baselines"]}))
    result = baselines.run(tmp_path)
    assert result == {"blocks": 2, "acs": 7}
    frame = gpd.pd.read_parquet(tmp_path / "baselines.parquet")
    assert list(frame["block_id"]) == ["blk_0001", "blk_0002"]
    m = json.loads((tmp_path / "meta.json").read_text())
    assert m["baseline_area"]["acs"] == 7
    assert m["skipped_steps"] == []


def test_cli_builds_a_bundle(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    result = CliRunner().invoke(
        app,
        [
            "all",
            "--area",
            "tiny",
            "--config",
            str(FIXTURES / "tiny.yaml"),
            "--data-dir",
            str(tmp_path),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (out / "meta.json").exists()
    assert "[bundle]" in result.output


def test_cli_rejects_an_unknown_step(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["nonsense", "--data-dir", str(tmp_path)])
    assert result.exit_code != 0


def assert_close(a: Any, b: Any, path: str = "meta", rel: float = 1e-9, abs_: float = 2e-4) -> None:
    """Exact for ints, strings and structure; tolerant for floats.

    abs_ covers values rounded to 4 decimals in meta (the sun table), which can flip by one last digit across platforms.
    """
    if isinstance(a, float) or isinstance(b, float):
        assert a == pytest.approx(b, rel=rel, abs=abs_), path
    elif isinstance(a, dict):
        assert a.keys() == b.keys(), path
        for k in a:
            assert_close(a[k], b[k], f"{path}.{k}", rel, abs_)
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            assert_close(x, y, f"{path}[{i}]", rel, abs_)
    else:
        assert a == b, path


def assert_table_close(
    a: gpd.GeoDataFrame,
    b: gpd.GeoDataFrame,
    name: str,
    rel: float = 1e-9,
    abs_: float = 1e-6,
    geom_tol: float = 1e-3,
) -> None:
    """Same columns, rows, CRS and ids; floats equal within abs_; coordinates equal within geom_tol.

    geom_tol defaults to 1 mm — wide enough to absorb GEOS/PROJ floating-point differences
    across platforms (Linux vs macOS builds) while still catching any real geometry change.
    """
    assert list(a.columns) == list(b.columns), f"{name}: columns"
    assert len(a) == len(b), f"{name}: rows"
    assert a.crs == b.crs, f"{name}: crs"
    geom = a.geometry.name
    for col in a.columns:
        if col == geom:
            assert shapely.equals_exact(a.geometry.values, b.geometry.values, tolerance=geom_tol).all(), f"{name}.{col}"
        elif a[col].dtype.kind == "f":
            np.testing.assert_allclose(
                a[col].to_numpy(), b[col].to_numpy(), rtol=rel, atol=abs_, equal_nan=True, err_msg=f"{name}.{col}"
            )
        else:
            assert a[col].equals(b[col]), f"{name}.{col}"


def test_engine_fixture_bundle_is_current(tiny: Tiny, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Rebuild the committed fixture and compare within float tolerance.

    Floats differ in the last digits across platforms (PROJ, GEOS and BLAS builds), so do not regenerate the
    fixture to silence this. Run make_tiny.py only when the pipeline's output really changed.
    """
    from ecozone_pipeline.steps import bundle

    monkeypatch.setenv("ECOZONE_PIPELINE_SHA", "tiny-fixture")
    fresh = bundle.run(tiny.cfg, tiny.paths, out_dir=tmp_path / "fresh")
    committed = FIXTURES.parents[2] / "engine" / "tests" / "fixtures" / "tiny"
    fresh_meta = json.loads((fresh / "meta.json").read_text())
    committed_meta = json.loads((committed / "meta.json").read_text())
    committed_meta["skipped_steps"] = [s for s in committed_meta["skipped_steps"] if s != "baselines"]
    assert_close(fresh_meta, committed_meta)
    for name in SCHEMA:
        fresh_table = gpd.read_parquet(fresh / f"{name}.parquet")
        committed_table = gpd.read_parquet(committed / f"{name}.parquet")
        assert_table_close(fresh_table, committed_table, name)
