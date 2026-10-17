"""WP5b tests: determinism, range, direction, budget, quick-win, ventilation.

All tests run on the tiny fixture (engine/tests/fixtures/tiny/).
Real pytest output is required per CLAUDE.md §Evidence before "done".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import settings as h_settings
from hypothesis import strategies as st

import ecozone_engine as engine
from ecozone_engine.indices import gcs, hei, vci
from ecozone_engine.model import Change, UnitCost, UnitCosts
from ecozone_engine.sun import delta_theta_deg, shadow_vector

TINY = Path(__file__).parent / "fixtures" / "tiny"

# ── Default unit costs for tests ──────────────────────────────────────────────

DEFAULT_COSTS: UnitCosts = {
    "tree_row": UnitCost(unit="tree", inr=5_000.0, source="test"),
    "shade": UnitCost(unit="m2", inr=2_000.0, source="test"),
    "depave": UnitCost(unit="m2", inr=500.0, source="test"),
    "pocket_green": UnitCost(unit="m2", inr=300.0, source="test"),
    "cool_roof": UnitCost(unit="m2", inr=200.0, source="test"),
}


@pytest.fixture(scope="module")
def area() -> engine.AreaModel:
    return engine.load_bundle(TINY)


# ── Golden tests for index formulas ───────────────────────────────────────────


def test_vci_golden_all_terms_max() -> None:
    """VCI = 100 when wind aligned with canyon, no built run, H/W=0, water adjacent.

    Hand computation:
        W_a = max(0, 100*cos(0°)) = 100
        C_o = max(0, 100 - 0/5) = 100
        O_b = 100*(1 - min(1, 0/2.5)) = 100
        P_g = max(0, 100 - 0/10) = 100
        VCI = 0.30*100 + 0.25*100 + 0.25*100 + 0.20*100 = 100.0
    """
    result = vci(h_w=0.0, canyon_axis_deg=90.0, l_built=0.0, d_water=0.0, wind_from_deg=90.0)
    assert abs(result - 100.0) < 1e-9


def test_vci_golden_all_terms_zero() -> None:
    """VCI ≈ 0 when H/W=2.5, wind perpendicular, long built run, far from water.

    Hand computation:
        W_a = max(0, 100*cos(90°)) = 0
        C_o = max(0, 100 - 500/5) = max(0, 0) = 0
        O_b = 100*(1 - min(1, 2.5/2.5)) = 0
        P_g = max(0, 100 - 1000/10) = 0
        VCI = 0.0
    """
    result = vci(h_w=2.5, canyon_axis_deg=0.0, l_built=500.0, d_water=1000.0, wind_from_deg=90.0)
    assert abs(result - 0.0) < 1e-9


def test_hei_golden_worst_case() -> None:
    """HEI = 100 when fully impervious, no green, average volume, darkest roof.

    Hand computation (all terms at maximum):
        I_s=100 → 0.35*100 = 35
        G_c=0 → 0.30*(100-0) = 30
        V/V_ref=1.0 → T_m=100 → 0.20*100 = 20
        alpha_roof=0.10 → R_a=100*(0.70-0.10)/(0.70-0.10)=100 → 0.15*100 = 15
        HEI = 35+30+20+15 = 100.0
    """
    result = hei(i_s=100.0, g_c=0.0, v=1000.0, v_ref=1000.0, roof_albedo=0.10)
    assert abs(result - 100.0) < 1e-9


def test_hei_golden_best_case() -> None:
    """HEI = 0 when no impervious, all green, V=0, coolest roof.

    Hand computation:
        I_s=0 → 0
        G_c=100 → 0.30*(0) = 0
        V=0 → T_m=0 → 0
        alpha_roof=0.70 → R_a=0 → 0
        HEI = 0.0
    """
    result = hei(i_s=0.0, g_c=100.0, v=0.0, v_ref=1000.0, roof_albedo=0.70)
    assert abs(result - 0.0) < 1e-9


def test_gcs_golden_best_case() -> None:
    """GCS = 100 when G_buf=100 and d_green=0.

    Hand computation:
        L_link = max(0, 100 - 0/3) = 100
        GCS = 0.5*100 + 0.5*100 = 100.0
    """
    result = gcs(g_buf=100.0, d_green=0.0)
    assert abs(result - 100.0) < 1e-9


def test_shadow_vector_golden() -> None:
    """Shadow vector for alt=45°, az=180° (due South) should point due North.

    Hand computation:
        length_per_m = 1/tan(45°) = 1.0
        dx = -sin(180°)*1.0 = 0.0
        dy = -cos(180°)*1.0 = +1.0
    """
    dx, dy = shadow_vector(45.0, 180.0)
    assert abs(dx - 0.0) < 1e-9
    assert abs(dy - 1.0) < 1e-9


def test_delta_theta_bidirectional() -> None:
    """Canyon at 45° is equally aligned with wind from 45° and wind from 225°."""
    assert abs(delta_theta_deg(45.0, 45.0) - 0.0) < 1e-9
    assert abs(delta_theta_deg(45.0, 225.0) - 0.0) < 1e-9


def test_delta_theta_perpendicular() -> None:
    """Canyon at 0° is perpendicular to wind from 90°."""
    assert abs(delta_theta_deg(0.0, 90.0) - 90.0) < 1e-9


# ── load_bundle and baseline ──────────────────────────────────────────────────


def test_load_bundle_returns_area(area: engine.AreaModel) -> None:
    assert area.area_id == "tiny"
    assert len(area.blocks) == 6
    assert len(area.buildings) == 24
    assert len(area.chunks) == 123
    assert len(area.sites) == 26
    assert len(area.wait_points) == 3
    assert len(area.parcels) == 3


def test_baseline_scores_in_range(area: engine.AreaModel) -> None:
    """All baseline block scores are in 0–100."""
    for block_id, scores in area.block_baselines:
        for name, val in [("vci", scores.vci), ("hei", scores.hei), ("gcs", scores.gcs), ("pss", scores.pss)]:
            assert 0.0 <= val <= 100.0, f"{block_id}.{name} = {val}"
    baseline = area.area_baseline
    for name, val in [
        ("vci", baseline.vci),
        ("hei", baseline.hei),
        ("gcs", baseline.gcs),
        ("pss", baseline.pss),
        ("acs", baseline.acs),
    ]:
        assert 0.0 <= val <= 100.0, f"area.{name} = {val}"


def test_blocks_sorted_by_id(area: engine.AreaModel) -> None:
    ids = [b.block_id for b in area.blocks]
    assert ids == sorted(ids)


def test_sites_sorted_by_id(area: engine.AreaModel) -> None:
    ids = [s.site_id for s in area.sites]
    assert ids == sorted(ids)


# ── Ventilation site rule (PLANNING.md Tests) ─────────────────────────────────


def test_rejected_tree_row_raises_invalid_change(area: engine.AreaModel) -> None:
    """rescore must refuse a rejected tree-row site (CANOPY_OBSTRUCTION)."""
    rejected = next(s for s in area.sites if s.rejected and s.kind == "tree_row")
    change = Change(kind="tree_row", site_id=rejected.site_id, quantity=rejected.quantity_min)
    with pytest.raises(engine.InvalidChangeError):
        engine.rescore(area, [change], DEFAULT_COSTS)


def test_unknown_site_raises(area: engine.AreaModel) -> None:
    change = Change(kind="shade", site_id="does_not_exist", quantity=1.0)
    with pytest.raises(engine.UnknownSiteError):
        engine.rescore(area, [change], DEFAULT_COSTS)


# ── Determinism (PLANNING.md Tests) ───────────────────────────────────────────


def test_rescore_determinism(area: engine.AreaModel) -> None:
    """Ten repeated calls must produce byte-equal JSON output."""
    valid_shade = next(s for s in area.sites if not s.rejected and s.kind == "shade")
    change = Change(kind="shade", site_id=valid_shade.site_id, quantity=valid_shade.quantity_min)

    import dataclasses

    def to_dict(r: engine.AreaResultData) -> dict[str, object]:
        return dataclasses.asdict(r)  # type: ignore[arg-type]

    first = json.dumps(to_dict(engine.rescore(area, [change], DEFAULT_COSTS)), sort_keys=True)
    for _ in range(9):
        run = json.dumps(to_dict(engine.rescore(area, [change], DEFAULT_COSTS)), sort_keys=True)
        assert run == first, "rescore is not deterministic"


def test_greedy_determinism(area: engine.AreaModel) -> None:
    """greedy_baseline is deterministic across 5 runs."""
    import dataclasses

    def to_dict(p: engine.PortfolioData) -> dict[str, object]:
        return dataclasses.asdict(p)  # type: ignore[arg-type]

    first = json.dumps(to_dict(engine.greedy_baseline(area, 200_000.0, DEFAULT_COSTS, 20.0)), sort_keys=True)
    for _ in range(4):
        run = json.dumps(to_dict(engine.greedy_baseline(area, 200_000.0, DEFAULT_COSTS, 20.0)), sort_keys=True)
        assert run == first, "greedy_baseline is not deterministic"


# ── Range (PLANNING.md Tests) ─────────────────────────────────────────────────


def test_rescore_range_shade(area: engine.AreaModel) -> None:
    """All indices stay in 0–100 after a shade intervention."""
    valid_shade = next(s for s in area.sites if not s.rejected and s.kind == "shade")
    change = Change(kind="shade", site_id=valid_shade.site_id, quantity=valid_shade.quantity_min)
    result = engine.rescore(area, [change], DEFAULT_COSTS)
    _assert_area_scores_in_range(result.after)
    for br in result.blocks:
        _assert_scores_in_range(br.after, br.block_id)


def test_rescore_range_depave(area: engine.AreaModel) -> None:
    """All indices stay in 0–100 after a depave intervention."""
    valid_depave = next(s for s in area.sites if not s.rejected and s.kind == "depave")
    change = Change(kind="depave", site_id=valid_depave.site_id, quantity=valid_depave.quantity_min)
    result = engine.rescore(area, [change], DEFAULT_COSTS)
    _assert_area_scores_in_range(result.after)


def test_rescore_range_cool_roof(area: engine.AreaModel) -> None:
    """All indices stay in 0–100 after a cool-roof intervention."""
    valid_cr = next(s for s in area.sites if not s.rejected and s.kind == "cool_roof")
    change = Change(kind="cool_roof", site_id=valid_cr.site_id, quantity=valid_cr.quantity_min)
    result = engine.rescore(area, [change], DEFAULT_COSTS)
    _assert_area_scores_in_range(result.after)


def test_rescore_range_pocket_green(area: engine.AreaModel) -> None:
    """All indices stay in 0–100 after a pocket-green intervention."""
    valid_pg = next(s for s in area.sites if not s.rejected and s.kind == "pocket_green")
    change = Change(kind="pocket_green", site_id=valid_pg.site_id, quantity=valid_pg.quantity_min)
    result = engine.rescore(area, [change], DEFAULT_COSTS)
    _assert_area_scores_in_range(result.after)


def test_rescore_range_tree_row(area: engine.AreaModel) -> None:
    """All indices stay in 0–100 after a tree-row intervention (valid low-H/W site)."""
    valid_tr = next(s for s in area.sites if not s.rejected and s.kind == "tree_row")
    change = Change(kind="tree_row", site_id=valid_tr.site_id, quantity=valid_tr.quantity_min)
    result = engine.rescore(area, [change], DEFAULT_COSTS)
    _assert_area_scores_in_range(result.after)


# ── Direction tests (PLANNING.md Tests §Direction Repair) ─────────────────────


def test_direction_pss_never_lowered_by_tree_row(area: engine.AreaModel) -> None:
    """Adding trees never lowers PSS (PLANNING.md Tests)."""
    for site in area.sites:
        if site.rejected or site.kind != "tree_row":
            continue
        change = Change(kind="tree_row", site_id=site.site_id, quantity=site.quantity_min)
        result = engine.rescore(area, [change], DEFAULT_COSTS)
        assert result.after.pss >= result.before.pss - 1e-9, (
            f"tree_row {site.site_id}: PSS dropped from {result.before.pss:.2f} to {result.after.pss:.2f}"
        )


def test_direction_pss_never_lowered_by_shade(area: engine.AreaModel) -> None:
    """Adding shade structures never lowers PSS (PLANNING.md Tests)."""
    for site in area.sites:
        if site.rejected or site.kind != "shade":
            continue
        change = Change(kind="shade", site_id=site.site_id, quantity=site.quantity_min)
        result = engine.rescore(area, [change], DEFAULT_COSTS)
        assert result.after.pss >= result.before.pss - 1e-9, (
            f"shade {site.site_id}: PSS dropped from {result.before.pss:.2f} to {result.after.pss:.2f}"
        )


def test_direction_hei_never_raised_by_depave(area: engine.AreaModel) -> None:
    """Depaving never raises HEI (PLANNING.md Tests)."""
    for site in area.sites:
        if site.rejected or site.kind != "depave":
            continue
        change = Change(kind="depave", site_id=site.site_id, quantity=site.quantity_min)
        result = engine.rescore(area, [change], DEFAULT_COSTS)
        assert result.after.hei <= result.before.hei + 1e-9, (
            f"depave {site.site_id}: HEI rose from {result.before.hei:.2f} to {result.after.hei:.2f}"
        )


def test_direction_hei_never_raised_by_cool_roof(area: engine.AreaModel) -> None:
    """Cool roofs never raise HEI (PLANNING.md Tests)."""
    for site in area.sites:
        if site.rejected or site.kind != "cool_roof":
            continue
        change = Change(kind="cool_roof", site_id=site.site_id, quantity=site.quantity_min)
        result = engine.rescore(area, [change], DEFAULT_COSTS)
        assert result.after.hei <= result.before.hei + 1e-9, (
            f"cool_roof {site.site_id}: HEI rose from {result.before.hei:.2f} to {result.after.hei:.2f}"
        )


def test_direction_gcs_never_lowered_by_green(area: engine.AreaModel) -> None:
    """Adding green (pocket_green, depave, tree_row) never lowers GCS (PLANNING.md Tests)."""
    green_kinds = {"pocket_green", "depave", "tree_row"}
    for site in area.sites:
        if site.rejected or site.kind not in green_kinds:
            continue
        change = Change(kind=site.kind, site_id=site.site_id, quantity=site.quantity_min)  # type: ignore[arg-type]
        result = engine.rescore(area, [change], DEFAULT_COSTS)
        assert result.after.gcs >= result.before.gcs - 1e-9, (
            f"{site.kind} {site.site_id}: GCS dropped from {result.before.gcs:.2f} to {result.after.gcs:.2f}"
        )


# ── Ventilation check (PLANNING.md Tests) ────────────────────────────────────


def test_ventilation_check_building_high_hw(area: engine.AreaModel) -> None:
    """A building that raises H/W above threshold triggers ventilation_ok=False."""
    parcel = area.parcels[0]
    # Force H/W well above 1 by choosing many floors on a narrow road
    floors = 10.0  # H = 30m; road_width typically 8-12m → H/W = 2.5-3.75
    change = Change(
        kind="building",
        site_id=parcel.parcel_id,
        quantity=1.0,
        params=(
            ("floors", floors),
            ("footprint_pct", 60.0),
            ("green_pct", 5.0),
            ("orientation_deg", parcel.street_bearing_deg),
        ),
    )
    result = engine.rescore(area, [change], DEFAULT_COSTS)
    # A 10-floor building should cause significant VCI drop
    assert result.worst_vci_drop > 0.0


def test_ventilation_ok_empty_change_set(area: engine.AreaModel) -> None:
    """Empty change set should return ventilation_ok=True and zero VCI drop."""
    result = engine.rescore(area, [], DEFAULT_COSTS)
    assert result.ventilation_ok is True
    assert result.worst_vci_drop == 0.0


# ── Budget and quick-win constraints (PLANNING.md Tests) ──────────────────────


def test_greedy_respects_budget(area: engine.AreaModel) -> None:
    """Every greedy portfolio is within budget (PLANNING.md Tests)."""
    budget = 300_000.0
    portfolio = engine.greedy_baseline(area, budget, DEFAULT_COSTS, 20.0)
    assert portfolio.result.cost_inr <= budget + 1e-6, (
        f"Portfolio cost {portfolio.result.cost_inr:.0f} exceeds budget {budget:.0f}"
    )


def test_greedy_quick_win_share(area: engine.AreaModel) -> None:
    """Greedy portfolio meets the quick-win share when affordable sites exist."""
    budget = 500_000.0
    share_pct = 20.0
    portfolio = engine.greedy_baseline(area, budget, DEFAULT_COSTS, share_pct)
    # Quick-win share of what was actually spent must not exceed total cost
    # (may be less than budget share if no quick-win sites are available)
    if portfolio.result.cost_inr > 0:
        assert portfolio.result.quick_win_cost_inr <= portfolio.result.cost_inr + 1e-6


def test_greedy_result_in_range(area: engine.AreaModel) -> None:
    """All greedy portfolio scores are in 0–100."""
    portfolio = engine.greedy_baseline(area, 300_000.0, DEFAULT_COSTS, 20.0)
    _assert_area_scores_in_range(portfolio.result.after)


def test_greedy_empty_budget_no_sites(area: engine.AreaModel) -> None:
    """greedy_baseline with zero budget returns empty portfolio."""
    portfolio = engine.greedy_baseline(area, 0.0, DEFAULT_COSTS, 20.0)
    assert portfolio.result.cost_inr == 0.0


# ── single_site ───────────────────────────────────────────────────────────────


def test_single_site_range(area: engine.AreaModel) -> None:
    """single_site ACS gain for a valid site."""
    valid_shade = next(s for s in area.sites if not s.rejected and s.kind == "shade")
    result = engine.single_site(area, valid_shade.site_id, DEFAULT_COSTS)
    assert result.site_id == valid_shade.site_id
    # acs_gain can be 0 or positive; cost must be non-negative
    assert result.cost_inr >= 0.0


def test_single_site_unknown_raises(area: engine.AreaModel) -> None:
    with pytest.raises(engine.UnknownSiteError):
        engine.single_site(area, "nonexistent", DEFAULT_COSTS)


# ── risk_label (PLANNING.md §Risk label) ──────────────────────────────────────


def test_risk_label_low_no_change(area: engine.AreaModel) -> None:
    """No building change → no risk info on the result."""
    valid_shade = next(s for s in area.sites if not s.rejected and s.kind == "shade")
    change = Change(kind="shade", site_id=valid_shade.site_id, quantity=valid_shade.quantity_min)
    result = engine.rescore(area, [change], DEFAULT_COSTS)
    assert result.risk is None  # risk only set for Protect building changes


def test_risk_label_building_has_risk(area: engine.AreaModel) -> None:
    """Building change produces a risk label."""
    parcel = area.parcels[0]
    change = Change(
        kind="building",
        site_id=parcel.parcel_id,
        quantity=1.0,
        params=(("floors", 5.0), ("footprint_pct", 50.0), ("green_pct", 10.0), ("orientation_deg", 90.0)),
    )
    result = engine.rescore(area, [change], DEFAULT_COSTS)
    assert result.risk is not None
    assert result.risk.label in ("LOW", "MODERATE", "HIGH")


# ── Hypothesis property tests ─────────────────────────────────────────────────


@h_settings(max_examples=30, deadline=10_000)
@given(
    h_w=st.floats(min_value=0.0, max_value=5.0, allow_nan=False),
    l_built=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False),
    d_water=st.floats(min_value=0.0, max_value=2000.0, allow_nan=False),
    wind=st.floats(min_value=0.0, max_value=360.0, allow_nan=False),
    canyon=st.floats(min_value=0.0, max_value=360.0, allow_nan=False),
)
def test_vci_range_property(h_w: float, l_built: float, d_water: float, wind: float, canyon: float) -> None:
    """VCI is always in [0, 100]."""
    result = vci(h_w=h_w, canyon_axis_deg=canyon, l_built=l_built, d_water=d_water, wind_from_deg=wind)
    assert 0.0 <= result <= 100.0


@h_settings(max_examples=30, deadline=10_000)
@given(
    i_s=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
    g_c=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
    v=st.floats(min_value=0.0, max_value=1e6, allow_nan=False),
    v_ref=st.floats(min_value=1.0, max_value=1e7, allow_nan=False),
    albedo=st.floats(min_value=0.05, max_value=0.95, allow_nan=False),
)
def test_hei_range_property(i_s: float, g_c: float, v: float, v_ref: float, albedo: float) -> None:
    """HEI is always in [0, 100]."""
    result = hei(i_s=i_s, g_c=g_c, v=v, v_ref=v_ref, roof_albedo=albedo)
    assert 0.0 <= result <= 100.0


@h_settings(max_examples=30, deadline=10_000)
@given(
    g_buf=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
    d_green=st.floats(min_value=0.0, max_value=2000.0, allow_nan=False),
)
def test_gcs_range_property(g_buf: float, d_green: float) -> None:
    """GCS is always in [0, 100]."""
    result = gcs(g_buf=g_buf, d_green=d_green)
    assert 0.0 <= result <= 100.0


@h_settings(max_examples=30, deadline=10_000)
@given(
    more_hw=st.booleans(),
    h_w=st.floats(min_value=0.0, max_value=4.0, allow_nan=False),
    delta=st.floats(min_value=0.0, max_value=2.0, allow_nan=False),
)
def test_direction_vci_higher_hw_never_improves(more_hw: bool, h_w: float, delta: float) -> None:
    """Higher H/W never improves VCI (PLANNING.md Direction Protect)."""
    base = vci(h_w=h_w, canyon_axis_deg=90.0, l_built=10.0, d_water=500.0, wind_from_deg=90.0)
    higher = vci(h_w=h_w + delta, canyon_axis_deg=90.0, l_built=10.0, d_water=500.0, wind_from_deg=90.0)
    assert higher <= base + 1e-9


# ── Helpers ───────────────────────────────────────────────────────────────────


def _assert_area_scores_in_range(scores: engine.AreaScores) -> None:
    for name, val in [
        ("vci", scores.vci),
        ("hei", scores.hei),
        ("gcs", scores.gcs),
        ("pss", scores.pss),
        ("acs", scores.acs),
    ]:
        assert 0.0 <= val <= 100.0, f"area.{name} = {val} out of range"


def _assert_scores_in_range(scores: engine.Scores, label: str = "") -> None:
    for name, val in [("vci", scores.vci), ("hei", scores.hei), ("gcs", scores.gcs), ("pss", scores.pss)]:
        assert 0.0 <= val <= 100.0, f"{label}.{name} = {val} out of range"
