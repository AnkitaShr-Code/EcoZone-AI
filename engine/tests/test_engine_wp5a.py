"""WP5a golden tests: indices, shadow geometry, range, determinism, load_bundle round-trip.

Each golden value is hand-computed from the PLANNING.md formulae and the tiny fixture
(engine/tests/fixtures/tiny/). Expected values are derived directly in the docstring
of each test so the calculation can be audited.

Fixture used: engine/tests/fixtures/tiny/
  - blk_0001: canyon_axis_deg=90.3685, wind_from_deg=300, L_built=14.9574, H_W=0.8166,
               d_water=1000, I_s=26.803, G_c=1.182, V=20313.6, V_ref=23094.8,
               roof_albedo=0.2543, G_buf=3.4722, d_green=135.478, wait_weight=7.0,
               built_form=dense_low_rise

Adapted from engine/core:engine/tests/test_engine_wp5a.py for the rescore branch.
Callers updated to rescore's function names and signatures; expected values unchanged.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

import ecozone_engine as engine
from ecozone_engine.drivers import block_drivers
from ecozone_engine.indices import gcs, hei, vci
from ecozone_engine.priority import (
    cooling_score,
    e_factor,
    v_factor,
    wait_weight_sum,
)
from ecozone_engine.shade import block_pss, pss_from_shading
from ecozone_engine.sun import shadow_vector

TINY = Path(__file__).parent / "fixtures" / "tiny"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tiny_area() -> engine.AreaModel:
    return engine.load_bundle(TINY)


# ---------------------------------------------------------------------------
# Formula golden tests (one per PLANNING.md §Scoring engine sub-formula)
# ---------------------------------------------------------------------------


def test_vci_blk_0001_golden() -> None:
    """VCI for blk_0001.

    wind_flow = (300+180)%360 = 120°
    delta_theta = min(|120-90.3685|, 180-|120-90.3685|) = min(29.6315, 150.3685) = 29.6315°
    W_a = 100·cos(29.6315°) = 86.9224
    C_o = 100 - 14.9574/5 = 97.0085
    O_b = 100·(1 - min(1, 0.8166/2.5)) = 100·(1-0.3266) = 67.3379
    P_g = max(0, 100 - 1000/10) = 0
    VCI = 0.30·86.9224 + 0.25·97.0085 + 0.25·67.3379 + 0.20·0 = 67.1633
    """
    result = vci(
        canyon_axis_deg=90.368535,
        wind_from_deg=300.0,
        l_built=14.957401,
        h_w=0.816552,
        d_water=1000.0,
    )
    assert abs(result - 67.1633) < 0.01, f"VCI={result}"


def test_hei_blk_0001_golden() -> None:
    """HEI for blk_0001.

    T_m = 100·(20313.635/23094.814) = 87.9576
    R_a = 100·(0.70-0.2543)/(0.70-0.10) = 100·0.4457/0.60 = 74.288
    HEI = 0.35·26.803 + 0.30·(100-1.182) + 0.20·87.958 + 0.15·74.288
        = 9.381 + 29.645 + 17.592 + 11.143 = 67.761
    """
    result = hei(
        i_s=26.803239,
        g_c=1.182178,
        v=20313.635176,
        v_ref=23094.81385641134,
        roof_albedo=0.254275,
    )
    assert abs(result - 67.761) < 0.01, f"HEI={result}"


def test_gcs_blk_0001_golden() -> None:
    """GCS for blk_0001.

    L_link = max(0, 100 - 135.478/3) = max(0, 100-45.159) = 54.841
    GCS = 0.5·3.472 + 0.5·54.841 = 1.736 + 27.421 = 29.157
    """
    result = gcs(g_buf=3.472207, d_green=135.477819)
    assert abs(result - 29.157) < 0.01, f"GCS={result}"


def test_e_factor_golden() -> None:
    """E_b = 1 + min(2, wait_weight/3).

    wait_weight=7 → 1 + min(2, 7/3) = 1 + 2 = 3.0
    wait_weight=3 → 1 + min(2, 1) = 2.0
    wait_weight=0 → 1.0
    """
    assert e_factor(7.0) == pytest.approx(3.0)
    assert e_factor(3.0) == pytest.approx(2.0)
    assert e_factor(0.0) == pytest.approx(1.0)


def test_v_factor_golden() -> None:
    """V_b = 1.25 for dense_low_rise, 1.0 otherwise."""
    assert v_factor("dense_low_rise") == pytest.approx(1.25)
    assert v_factor("other") == pytest.approx(1.0)


def test_priority_blk_0001_golden(tiny_area: engine.AreaModel) -> None:
    """P_b = HEI · (1 - PSS/100) · E_b · V_b.

    blk_0001: HEI=67.761, PSS=9.374 (from chunk shade), E=3.0, V=1.25
    P = 67.761 · (1-0.09374) · 3.0 · 1.25 ≈ 230.3

    Adapted: no blk.priority attribute in rescore; compute from block_baselines and helpers.
    """
    blk = next(b for b in tiny_area.blocks if b.block_id == "blk_0001")
    baseline_dict = dict(tiny_area.block_baselines)
    sc = baseline_dict["blk_0001"]
    wsum = wait_weight_sum(blk.geometry, list(tiny_area.wait_points))
    ew = e_factor(wsum)
    vv = v_factor(blk.built_form)
    priority = sc.hei * (1.0 - sc.pss / 100.0) * ew * vv
    assert abs(priority - 230.0) < 2.0, f"priority={priority}"


def test_chunk_pss_golden() -> None:
    """PSS_chunk = 100 * shaded_times / 3.

    Adapted: core's chunk_pss((True,False,False)) → rescore's pss_from_shading((True,False,False)).
    (True,False,False) → 33.33, (True,True,True) → 100, (False,False,False) → 0
    """
    assert pss_from_shading((True, False, False)) == pytest.approx(100 / 3)
    assert pss_from_shading((True, True, True)) == pytest.approx(100.0)
    assert pss_from_shading((False, False, False)) == pytest.approx(0.0)


def test_block_pss_length_weighted_golden() -> None:
    """Block PSS = length-weighted mean of chunk PSS values.

    Two chunks: length=10, pss=100 and length=10, pss=0 → block PSS = 50.

    Adapted: rescore's block_pss(block_id, chunks, chunk_shading) takes shading separately.
    """
    from shapely.geometry import LineString

    from ecozone_engine.model import ChunkRow

    def _chunk(cid: str, length: float) -> ChunkRow:
        return ChunkRow(
            chunk_id=cid,
            geometry=LineString([(0, 0), (1, 0)]),
            block_id="blk_x",
            length_m=length,
            near_wait=False,
        )

    chunks = [_chunk("a", 10.0), _chunk("b", 10.0)]
    shading = {"a": (True, True, True), "b": (False, False, False)}
    assert block_pss("blk_x", chunks, shading) == pytest.approx(50.0)


def test_cooling_score_golden() -> None:
    """C_b = 0.45·(100-HEI) + 0.35·PSS + 0.20·GCS.

    HEI=50, PSS=40, GCS=60 → 0.45·50 + 0.35·40 + 0.20·60 = 22.5+14+12 = 48.5
    """
    assert cooling_score(50.0, 40.0, 60.0) == pytest.approx(48.5)


# ---------------------------------------------------------------------------
# Shadow geometry golden test (PLANNING.md §Shadow sources)
# ---------------------------------------------------------------------------


def test_shadow_offset_15h_golden() -> None:
    """shadow_vector at 15:00 (alt=53.7919°, az=261.2205°) for a 9 m building.

    length = 9 / tan(53.7919°) = 9 / 1.3606 ≈ 6.589 m
    dx = -sin(261.2205°) · 6.589 ≈  6.512 m  (shadow goes east)
    dy = -cos(261.2205°) · 6.589 ≈  1.006 m  (shadow goes slightly north)

    Adapted: core's shadow_offset(az, alt, height) → rescore's shadow_vector(alt, az) × height.
    Direction is verified within 1% of the hand-computed value.
    """
    alt_deg = 53.7919
    az_deg = 261.2205
    height_m = 9.0

    sv_dx, sv_dy = shadow_vector(altitude_deg=alt_deg, azimuth_deg=az_deg)
    dx, dy = sv_dx * height_m, sv_dy * height_m

    expected_length = height_m / math.tan(math.radians(alt_deg))
    expected_dx = -math.sin(math.radians(az_deg)) * expected_length
    expected_dy = -math.cos(math.radians(az_deg)) * expected_length

    assert abs(dx - expected_dx) / expected_length < 0.001, f"dx={dx} expected≈{expected_dx}"
    assert abs(dy - expected_dy) / expected_length < 0.001, f"dy={dy} expected≈{expected_dy}"
    assert abs(math.hypot(dx, dy) - expected_length) / expected_length < 0.001


def test_shadow_offset_direction_13h() -> None:
    """Sun at 13:00 (az=215.98°, alt=79.35°) → shadow is north-east of the building.

    dx = -sin(215.98°) · L > 0 (eastward component)
    dy = -cos(215.98°) · L > 0 (northward component)

    Adapted: shadow_vector returns per-metre; direction check is the same.
    """
    sv_dx, sv_dy = shadow_vector(altitude_deg=79.3454, azimuth_deg=215.9799)
    assert sv_dx > 0, "shadow should extend east at 13:00 (sun in SW)"
    assert sv_dy > 0, "shadow should extend north at 13:00 (sun in SW)"


# ---------------------------------------------------------------------------
# load_bundle round-trip tests
# ---------------------------------------------------------------------------


def test_load_bundle_returns_area_model(tiny_area: engine.AreaModel) -> None:
    assert isinstance(tiny_area, engine.AreaModel)
    assert tiny_area.area_id == "tiny"
    assert len(tiny_area.blocks) == 6
    assert len(tiny_area.buildings) == 24
    assert len(tiny_area.chunks) == 123
    assert len(tiny_area.sites) == 26
    assert len(tiny_area.wait_points) == 3


def test_load_bundle_blocks_have_scores(tiny_area: engine.AreaModel) -> None:
    """Adapted: scores are in block_baselines, not on block rows."""
    baseline_dict = dict(tiny_area.block_baselines)
    for b in tiny_area.blocks:
        sc = baseline_dict[b.block_id]
        assert 0.0 <= sc.vci <= 100.0, f"{b.block_id} vci={sc.vci}"
        assert 0.0 <= sc.hei <= 100.0, f"{b.block_id} hei={sc.hei}"
        assert 0.0 <= sc.gcs <= 100.0, f"{b.block_id} gcs={sc.gcs}"
        assert 0.0 <= sc.pss <= 100.0, f"{b.block_id} pss={sc.pss}"


def test_load_bundle_priority_classes_cover_all_blocks(tiny_area: engine.AreaModel) -> None:
    """Adapted: priority_class comes from hotspots(), not block rows."""
    spots = engine.hotspots(tiny_area, len(tiny_area.blocks))
    classes = {s.priority_class for s in spots}
    assert "high" in classes and "low" in classes


def test_load_bundle_baseline_precomputed(tiny_area: engine.AreaModel) -> None:
    """Adapted: area_baseline replaces core's tiny_area.baseline.area."""
    assert 0.0 <= tiny_area.area_baseline.acs <= 100.0


# ---------------------------------------------------------------------------
# Range test: 0–100 for all indices on all blocks
# ---------------------------------------------------------------------------


def test_all_indices_in_range_0_to_100(tiny_area: engine.AreaModel) -> None:
    """Adapted: scores in block_baselines."""
    for block_id, sc in tiny_area.block_baselines:
        for name, val in [("vci", sc.vci), ("hei", sc.hei), ("gcs", sc.gcs), ("pss", sc.pss)]:
            assert 0.0 <= val <= 100.0, f"{block_id}.{name}={val} out of range"


def test_acs_in_range_0_to_100(tiny_area: engine.AreaModel) -> None:
    """Adapted: area_baseline replaces core's tiny_area.baseline.area."""
    assert 0.0 <= tiny_area.area_baseline.acs <= 100.0


# ---------------------------------------------------------------------------
# Determinism: 10 independent loads must produce byte-equal JSON
# ---------------------------------------------------------------------------


def test_determinism_10_runs() -> None:
    """load_bundle is deterministic: 10 independent loads produce byte-equal JSON results.

    Adapted: scores come from block_baselines dict instead of block attributes.
    """

    def _snapshot(area: engine.AreaModel) -> str:
        data = {
            block_id: {
                "vci": sc.vci,
                "hei": sc.hei,
                "gcs": sc.gcs,
                "pss": sc.pss,
            }
            for block_id, sc in area.block_baselines
        }
        return json.dumps(data, sort_keys=True)

    first = _snapshot(engine.load_bundle(TINY))
    for run in range(1, 10):
        snapshot = _snapshot(engine.load_bundle(TINY))
        assert snapshot == first, f"run {run} produced different output"


# ---------------------------------------------------------------------------
# compute_baselines and hotspots
# ---------------------------------------------------------------------------


def test_compute_baselines_returns_baseline_data(tiny_area: engine.AreaModel) -> None:
    bd = engine.compute_baselines(tiny_area)
    assert isinstance(bd, engine.BaselineData)
    assert len(bd.blocks) == 6
    assert 0.0 <= bd.area.acs <= 100.0


def test_hotspots_ranking(tiny_area: engine.AreaModel) -> None:
    spots = engine.hotspots(tiny_area, 3)
    assert len(spots) == 3
    assert spots[0].rank == 1
    assert spots[0].priority >= spots[1].priority >= spots[2].priority


# ---------------------------------------------------------------------------
# Drivers
# ---------------------------------------------------------------------------


def test_drivers_blk_0001(tiny_area: engine.AreaModel) -> None:
    """Adapted: block_drivers() takes baseline attributes; scores from block_baselines.

    # PSS=9.37 < 30 → SHADE_GAIN; wait_weight_sum>0 → WAIT_POINT_COVERED
    # d_green=135.5 > 100 → GREEN_LINK; roof_albedo=0.254 < 0.30 → ALBEDO_GAIN
    # I_s=26.8 < 50 → no IMPERVIOUS_LOSS
    """
    blk = next(b for b in tiny_area.blocks if b.block_id == "blk_0001")
    baseline_dict = dict(tiny_area.block_baselines)
    sc = baseline_dict["blk_0001"]
    wsum = wait_weight_sum(blk.geometry, list(tiny_area.wait_points))
    drivers = block_drivers(
        pss=sc.pss,
        i_s=blk.I_s,
        roof_albedo=blk.roof_albedo,
        d_green=blk.d_green,
        wait_weight_sum=wsum,
    )
    assert "SHADE_GAIN" in drivers
    assert "WAIT_POINT_COVERED" in drivers
    assert "GREEN_LINK" in drivers
    assert "ALBEDO_GAIN" in drivers
    # I_s=26.8 < 50 → no IMPERVIOUS_LOSS
    assert "IMPERVIOUS_LOSS" not in drivers
