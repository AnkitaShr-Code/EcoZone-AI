"""Every prototype setting, each citing its docs/PLANNING.md section (engine/RULES.md).

All weights, thresholds, radii and crown sizes live here and nowhere else.
A numeric literal in scoring code (other than 0, 1, 100 and unit conversions) is a blocker.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EngineSettings:
    # ── VCI weights (PLANNING.md §VCI) ────────────────────────────────────────
    w_vci_wa: float = 0.30
    w_vci_co: float = 0.25
    w_vci_ob: float = 0.25
    w_vci_pg: float = 0.20
    l_built_scale: float = 5.0  # C_o = max(0, 100 - L_built/5)
    h_w_scale: float = 2.5  # O_b = 100*(1 - min(1, H_W/2.5))
    d_water_scale: float = 10.0  # P_g = max(0, 100 - d_water/10)

    # ── HEI weights (PLANNING.md §HEI) ───────────────────────────────────────
    w_hei_is: float = 0.35
    w_hei_gc: float = 0.30
    w_hei_tm: float = 0.20
    w_hei_ra: float = 0.15
    albedo_ref_high: float = 0.70  # dark roof reference (Ra numerator)
    albedo_ref_low: float = 0.10  # cool roof reference (Ra denominator floor)

    # ── GCS weights (PLANNING.md §GCS) ───────────────────────────────────────
    w_gcs_gbuf: float = 0.50
    w_gcs_llink: float = 0.50
    d_green_scale: float = 3.0  # L_link = max(0, 100 - d_green/3)

    # ── ACS weights (PLANNING.md §ACS) ───────────────────────────────────────
    w_acs_hei: float = 0.45
    w_acs_pss: float = 0.35
    w_acs_gcs: float = 0.20

    # ── Priority / exposure (PLANNING.md §Priority) ───────────────────────────
    wait_radius_m: float = 150.0
    e_b_divisor: float = 3.0
    e_b_max: float = 2.0
    v_b_dense: float = 1.25
    v_b_other: float = 1.0

    # ── Wait-point weights (PLANNING.md §Priority, prototype settings) ────────
    wt_school: float = 3.0
    wt_hospital: float = 3.0
    wt_clinic: float = 2.0
    wt_college: float = 2.0
    wt_market: float = 2.0
    wt_bus_stop: float = 1.0

    # ── Dense low-rise thresholds (PLANNING.md §Priority, prototype settings)
    #    Deccan config differs — changing these needs a team decision.
    dense_coverage: float = 0.50
    dense_footprint_m2: float = 60.0
    dense_floors: float = 2.0

    # ── Risk label thresholds (PLANNING.md §Risk label, prototype settings) ───
    risk_moderate_min: float = 10.0
    risk_high_min: float = 25.0

    # ── Ventilation check (PLANNING.md §ACS; engine/RULES.md §Ventilation) ───
    vci_drop_threshold: float = 10.0

    # ── Shadow / tree geometry (PLANNING.md §PSS, §Interventions) ────────────
    metres_per_floor: float = 3.0
    crown_radius_m: float = 3.5  # tree crown disc radius
    crown_height_m: float = 5.0  # crown centre height above ground
    shade_structure_height_m: float = 3.0  # shade structure canopy height

    # ── Spatial radii (PLANNING.md §Terms, §Area rescoring) ──────────────────
    green_buffer_radius_m: float = 300.0
    wait_shade_radius_m: float = 30.0  # max dist from shade site to wait point

    # ── Canopy site rule (PLANNING.md Intervention library) ───────────────────
    canopy_hw_threshold: float = 1.0  # tree rows refused where H/W >= this

    # ── Quick-win time-to-benefit qualifiers (PLANNING.md §ACS) ─────────────
    quick_win_ttb: tuple[str, ...] = ("weeks", "season")

    # ── Prototype intervention attributes ─────────────────────────────────────
    cool_roof_albedo: float = 0.60  # applied roof albedo after cool coating
    depave_green_frac: float = 0.70  # fraction of depaved area that becomes green

    # ── Block-level driver thresholds (PLANNING.md §Primary drivers) ──────────
    driver_shade_pss_threshold: float = 30.0  # PSS below this → SHADE_GAIN
    driver_impervious_threshold: float = 50.0  # I_s above this → IMPERVIOUS_LOSS
    driver_albedo_threshold: float = 0.30  # roof_albedo below this → ALBEDO_GAIN
    driver_green_link_threshold: float = 100.0  # d_green above this → GREEN_LINK

    # ── Greedy skip threshold (engine/RULES.md §Greedy) ──────────────────────
    greedy_min_gain: float = 0.0


SETTINGS = EngineSettings()
