"""VCI, HEI, GCS as pure functions of block attributes (PLANNING.md §Scoring engine)."""

from __future__ import annotations

import math

from .settings import SETTINGS


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _delta_theta(canyon_axis_deg: float, wind_from_deg: float) -> float:
    """Angle Δθ between the prevailing wind flow and the street canyon axis, in [0°, 90°].

    Wind flow direction = (wind_from_deg + 180) mod 360.
    Canyon is bidirectional so we take the acute angle to the nearest axis direction.
    """
    wind_flow = (wind_from_deg + 180.0) % 360.0
    raw = abs(wind_flow - canyon_axis_deg) % 360.0
    if raw > 180.0:
        raw = 360.0 - raw  # now in [0, 180]
    return min(raw, 180.0 - raw)  # canyon bidirectional → [0, 90]


def vci(
    canyon_axis_deg: float,
    wind_from_deg: float,
    l_built: float,
    h_w: float,
    d_water: float,
) -> float:
    """Ventilation Corridor Index, 0–100 (PLANNING.md §VCI).

    VCI = 0.30·W_a + 0.25·C_o + 0.25·O_b + 0.20·P_g
      W_a = max(0, 100·cos(Δθ))
      C_o = max(0, 100 - L_built / 5)
      O_b = 100·(1 - min(1, H/W / 2.5))
      P_g = max(0, 100 - d_water / 10)
    """
    delta = _delta_theta(canyon_axis_deg, wind_from_deg)
    w_a = max(0.0, 100.0 * math.cos(math.radians(delta)))
    c_o = max(0.0, 100.0 - l_built / SETTINGS.vci_l_built_scale)
    o_b = 100.0 * (1.0 - min(1.0, h_w / SETTINGS.vci_h_w_max))
    p_g = max(0.0, 100.0 - d_water / SETTINGS.vci_d_water_scale)
    score = SETTINGS.vci_w_a * w_a + SETTINGS.vci_c_o * c_o + SETTINGS.vci_o_b * o_b + SETTINGS.vci_p_g * p_g
    return _clamp(score)


def hei(i_s: float, g_c: float, v: float, v_ref: float, roof_albedo: float) -> float:
    """Heat Exposure Index, 0–100 (PLANNING.md §HEI).

    HEI = 0.35·I_s + 0.30·(100 - G_c) + 0.20·T_m + 0.15·R_a
      T_m = 100·min(1, V / V_ref)
      R_a = 100·clamp((0.70 - α_roof) / (0.70 - 0.10), 0, 1)
    """
    t_m = 100.0 * min(1.0, v / v_ref) if v_ref > 0.0 else 0.0
    r_a_num = SETTINGS.hei_r_a_high - roof_albedo
    r_a_den = SETTINGS.hei_r_a_high - SETTINGS.hei_r_a_low
    r_a = 100.0 * _clamp(r_a_num / r_a_den, 0.0, 1.0)
    score = SETTINGS.hei_i_s * i_s + SETTINGS.hei_g_c * (100.0 - g_c) + SETTINGS.hei_t_m * t_m + SETTINGS.hei_r_a * r_a
    return _clamp(score)


def gcs(g_buf: float, d_green: float) -> float:
    """Green Connectivity Score, 0–100 (PLANNING.md §GCS).

    GCS = 0.5·G_buf + 0.5·L_link
      L_link = max(0, 100 - d_green / 3)
    """
    l_link = max(0.0, 100.0 - d_green / SETTINGS.gcs_d_green_scale)
    score = SETTINGS.gcs_g_buf * g_buf + SETTINGS.gcs_l_link * l_link
    return _clamp(score)
