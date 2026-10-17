"""Priority, E-factor, V-factor, ACS (PLANNING.md §Repair priority and Area Cooling Score)."""

from __future__ import annotations

from collections.abc import Sequence

from .model import BlockRow, PriorityClass
from .settings import SETTINGS


def e_factor(wait_weight: float) -> float:
    """E_b = 1 + min(2, wait_weight / 3).

    wait_weight is the precomputed sum of w_k for waiting points within 150 m.
    """
    return 1.0 + min(SETTINGS.priority_e_cap, wait_weight / SETTINGS.priority_e_denominator)


def v_factor(built_form: str) -> float:
    """V_b = 1.25 for dense_low_rise, 1.0 otherwise."""
    return SETTINGS.priority_v_dense if built_form == "dense_low_rise" else 1.0


def priority(hei: float, pss: float, wait_weight: float, built_form: str) -> float:
    """P_b = HEI_b · (1 - PSS_b/100) · E_b · V_b  (PLANNING.md §Priority)."""
    return hei * (1.0 - pss / 100.0) * e_factor(wait_weight) * v_factor(built_form)


def cooling_score(hei: float, pss: float, gcs: float) -> float:
    """C_b = 0.45·(100-HEI) + 0.35·PSS + 0.20·GCS  (PLANNING.md §ACS)."""
    return SETTINGS.acs_hei * (100.0 - hei) + SETTINGS.acs_pss * pss + SETTINGS.acs_gcs * gcs


def acs(blocks: Sequence[BlockRow]) -> float:
    """ACS = Σ(w_b·C_b) / Σ(w_b)  (PLANNING.md §ACS).

    w_b = E_b · V_b; blocks already carry precomputed hei, pss, gcs.
    Returns 0.0 for an empty area.
    """
    total_w = 0.0
    total_wc = 0.0
    for b in blocks:
        w = e_factor(b.wait_weight) * v_factor(b.built_form)
        c = cooling_score(b.hei, b.pss, b.gcs)
        total_w += w
        total_wc += w * c
    return total_wc / total_w if total_w > 0.0 else 0.0


def area_vci(blocks: Sequence[BlockRow]) -> float:
    """Area VCI: area-weighted mean of block VCI."""
    total_area = sum(b.area_m2 for b in blocks)
    if total_area == 0.0:
        return 0.0
    return sum(b.vci * b.area_m2 for b in blocks) / total_area


def area_hei(blocks: Sequence[BlockRow]) -> float:
    """Area HEI: area-weighted mean of block HEI."""
    total_area = sum(b.area_m2 for b in blocks)
    if total_area == 0.0:
        return 0.0
    return sum(b.hei * b.area_m2 for b in blocks) / total_area


def area_gcs(blocks: Sequence[BlockRow]) -> float:
    """Area GCS: area-weighted mean of block GCS."""
    total_area = sum(b.area_m2 for b in blocks)
    if total_area == 0.0:
        return 0.0
    return sum(b.gcs * b.area_m2 for b in blocks) / total_area


def priority_classes(
    blocks: Sequence[BlockRow],
) -> dict[str, PriorityClass]:
    """Assign high/medium/low by tercile of priority across all blocks.

    Top third → high, bottom third → low, middle → medium.
    Ties are broken by block_id (sorted ascending) so the split is deterministic.
    """
    if not blocks:
        return {}
    ranked = sorted(blocks, key=lambda b: (-b.priority, b.block_id))
    n = len(ranked)
    classes: dict[str, PriorityClass] = {}
    for i, b in enumerate(ranked):
        if i < n / 3:
            classes[b.block_id] = "high"
        elif i < 2 * n / 3:
            classes[b.block_id] = "medium"
        else:
            classes[b.block_id] = "low"
    return classes
