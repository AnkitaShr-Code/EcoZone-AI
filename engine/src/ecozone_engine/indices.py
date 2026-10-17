"""Pure index functions: vci(), hei(), gcs() (docs/PLANNING.md §Scoring engine).

Each function takes raw attribute values and returns a clamped 0–100 float.
No I/O, no side effects, no global state (engine/RULES.md, "Pure").
"""

from __future__ import annotations

import math

from .settings import SETTINGS as S
from .sun import delta_theta_deg

# ── Ventilation Corridor Index (PLANNING.md §VCI) ─────────────────────────────


def vci(
    *,
    h_w: float,
    canyon_axis_deg: float,
    l_built: float,
    d_water: float,
    wind_from_deg: float,
) -> float:
    """VCI for one block.

    Golden test (all terms maximised):
        h_w=0, l_built=0, d_water=0, wind aligned with canyon →
        w_a=100, c_o=100, o_b=100, p_g=100 → VCI=100.0
    """
    dt = delta_theta_deg(canyon_axis_deg, wind_from_deg)
    w_a = max(0.0, 100.0 * math.cos(math.radians(dt)))
    c_o = max(0.0, 100.0 - l_built / S.l_built_scale)
    o_b = 100.0 * (1.0 - min(1.0, h_w / S.h_w_scale))
    p_g = max(0.0, 100.0 - d_water / S.d_water_scale)
    raw = S.w_vci_wa * w_a + S.w_vci_co * c_o + S.w_vci_ob * o_b + S.w_vci_pg * p_g
    return max(0.0, min(100.0, raw))


# ── Heat Exposure Index (PLANNING.md §HEI) ────────────────────────────────────


def hei(
    *,
    i_s: float,
    g_c: float,
    v: float,
    v_ref: float,
    roof_albedo: float,
) -> float:
    """HEI for one block.

    Golden test (worst case):
        i_s=100, g_c=0, v/v_ref=1, roof_albedo=albedo_ref_low=0.10 →
        t_m=100, r_a=100 → HEI = 0.35·100 + 0.30·100 + 0.20·100 + 0.15·100 = 100.0
    """
    t_m = 100.0 * min(1.0, v / v_ref) if v_ref > 0.0 else 0.0
    span = S.albedo_ref_high - S.albedo_ref_low
    r_a = 100.0 * max(0.0, min(1.0, (S.albedo_ref_high - roof_albedo) / span))
    raw = S.w_hei_is * i_s + S.w_hei_gc * (100.0 - g_c) + S.w_hei_tm * t_m + S.w_hei_ra * r_a
    return max(0.0, min(100.0, raw))


# ── Green Connectivity Score (PLANNING.md §GCS) ───────────────────────────────


def gcs(*, g_buf: float, d_green: float) -> float:
    """GCS for one block.

    Golden test (best case):
        g_buf=100, d_green=0 → l_link=100 → GCS=100.0
    """
    l_link = max(0.0, 100.0 - d_green / S.d_green_scale)
    raw = S.w_gcs_gbuf * g_buf + S.w_gcs_llink * l_link
    return max(0.0, min(100.0, raw))


# ── Block cooling score (PLANNING.md §ACS) ────────────────────────────────────


def block_cooling(hei_val: float, pss_val: float, gcs_val: float) -> float:
    """C_b = 0.45*(100-HEI) + 0.35*PSS + 0.20*GCS (clamped 0-100)."""
    raw = S.w_acs_hei * (100.0 - hei_val) + S.w_acs_pss * pss_val + S.w_acs_gcs * gcs_val
    return max(0.0, min(100.0, raw))
