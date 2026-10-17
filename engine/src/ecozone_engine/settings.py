"""Every prototype setting, each citing its docs/PLANNING.md section (engine/RULES.md, "Settings, not literals").

One frozen dataclass so settings hash into the bundle meta.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EngineSettings:
    # ---- VCI weights (PLANNING.md §Ventilation Corridor Index) ----
    # VCI = 0.30·W_a + 0.25·C_o + 0.25·O_b + 0.20·P_g
    vci_w_a: float = 0.30
    vci_c_o: float = 0.25
    vci_o_b: float = 0.25
    vci_p_g: float = 0.20
    # C_o = max(0, 100 - L_built / 5)
    vci_l_built_scale: float = 5.0
    # O_b = 100·(1 - min(1, H/W / 2.5))
    vci_h_w_max: float = 2.5
    # P_g = max(0, 100 - d_water / 10)
    vci_d_water_scale: float = 10.0

    # ---- HEI weights (PLANNING.md §Heat Exposure Index) ----
    # HEI = 0.35·I_s + 0.30·(100 - G_c) + 0.20·T_m + 0.15·R_a
    hei_i_s: float = 0.35
    hei_g_c: float = 0.30
    hei_t_m: float = 0.20
    hei_r_a: float = 0.15
    # R_a = 100·clamp((0.70 - alpha_roof) / (0.70 - 0.10), 0, 1)
    hei_r_a_high: float = 0.70
    hei_r_a_low: float = 0.10

    # ---- GCS weights (PLANNING.md §Green Connectivity Score) ----
    # GCS = 0.5·G_buf + 0.5·L_link;  L_link = max(0, 100 - d_green / 3)
    gcs_g_buf: float = 0.50
    gcs_l_link: float = 0.50
    gcs_d_green_scale: float = 3.0

    # ---- PSS (PLANNING.md §Pedestrian Shade Score) ----
    pss_n_times: int = 3

    # ---- Priority and ACS (PLANNING.md §Repair priority and Area Cooling Score) ----
    # E_b = 1 + min(2, wait_weight / 3)
    priority_e_denominator: float = 3.0
    priority_e_cap: float = 2.0
    # V_b = 1.25 for dense_low_rise, 1.0 otherwise
    priority_v_dense: float = 1.25
    # Waiting-point weights: school 3, hospital 3, market 2, bus_stop 1
    wp_weight_school: float = 3.0
    wp_weight_hospital: float = 3.0
    wp_weight_market: float = 2.0
    wp_weight_bus_stop: float = 1.0
    # ACS: C_b = 0.45·(100-HEI) + 0.35·PSS + 0.20·GCS
    acs_hei: float = 0.45
    acs_pss: float = 0.35
    acs_gcs: float = 0.20

    # ---- Shadow geometry (PLANNING.md §PSS domain rules) ----
    tree_crown_radius_m: float = 2.5
    tree_crown_height_m: float = 4.0
    shade_structure_height_m: float = 3.0

    # ---- Ventilation drop threshold (PLANNING.md §ACS constraints) ----
    vci_drop_threshold: float = 10.0

    # ---- Driver tag thresholds (PLANNING.md §Primary drivers) ----
    driver_shade_pss_threshold: float = 30.0
    driver_impervious_threshold: float = 50.0
    driver_albedo_threshold: float = 0.30
    driver_green_link_threshold: float = 100.0


SETTINGS = EngineSettings()
