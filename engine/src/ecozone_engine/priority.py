"""Priority ranking, ACS, and risk label (docs/PLANNING.md §Priority, §Risk label)."""

from __future__ import annotations

from .model import AreaScores, BlockRow, IndexKey, RiskInfo, RiskLabel, Scores, WaitPointRow
from .settings import SETTINGS as S


def wait_weight(block: BlockRow, wait_points: list[WaitPointRow]) -> float:
    """E_b = 1 + min(e_b_max, sum(w_k for wait points within 150m) / e_b_divisor)."""
    total = 0.0
    for wp in wait_points:
        dist = block.geometry.centroid.distance(wp.geometry)
        if dist <= S.wait_radius_m:
            total += wp.weight
    return 1.0 + min(S.e_b_max, total / S.e_b_divisor)


def vulnerability(block: BlockRow) -> float:
    """V_b = 1.25 for dense low-rise, 1.0 otherwise (PLANNING.md §Priority)."""
    if (
        block.built_form == "dense_low_rise"
        or (
            block.coverage >= S.dense_coverage
            and block.median_footprint_m2 <= S.dense_footprint_m2
            and block.median_floors <= S.dense_floors
        )
    ):
        return S.v_b_dense
    return S.v_b_other


def block_priority(block: BlockRow, scores: Scores, wait_points: list[WaitPointRow]) -> float:
    """P_b = HEI * (1 - PSS/100) * E_b * V_b."""
    ew = wait_weight(block, wait_points)
    vv = vulnerability(block)
    return scores.hei * (1.0 - scores.pss / 100.0) * ew * vv


def area_acs(
    blocks: list[BlockRow],
    block_scores: dict[str, Scores],
    wait_points: list[WaitPointRow],
) -> float:
    """Area Cooling Score = weighted mean of block cooling scores (PLANNING.md §ACS)."""
    from .indices import block_cooling

    w_sum = 0.0
    c_sum = 0.0
    for b in sorted(blocks, key=lambda r: r.block_id):
        sc = block_scores.get(b.block_id)
        if sc is None:
            continue
        ew = wait_weight(b, wait_points)
        vv = vulnerability(b)
        w = ew * vv
        cooling = block_cooling(sc.hei, sc.pss, sc.gcs)
        c_sum += w * cooling
        w_sum += w
    if w_sum == 0.0:
        return 0.0
    return max(0.0, min(100.0, c_sum / w_sum))


def area_weighted_scores(
    blocks: list[BlockRow],
    block_scores: dict[str, Scores],
    wait_points: list[WaitPointRow],
    chunk_pss: float,
) -> AreaScores:
    """Compute area-level averaged scores and ACS."""
    w_sum = 0.0
    vci_sum = hei_sum = gcs_sum = pss_sum = 0.0
    for b in sorted(blocks, key=lambda r: r.block_id):
        sc = block_scores.get(b.block_id)
        if sc is None:
            continue
        ew = wait_weight(b, wait_points)
        vv = vulnerability(b)
        w = ew * vv
        vci_sum += w * sc.vci
        hei_sum += w * sc.hei
        gcs_sum += w * sc.gcs
        pss_sum += w * sc.pss
        w_sum += w

    if w_sum == 0.0:
        return AreaScores(vci=0.0, hei=0.0, gcs=0.0, pss=0.0, acs=0.0)

    acs_val = area_acs(blocks, block_scores, wait_points)
    return AreaScores(
        vci=max(0.0, min(100.0, vci_sum / w_sum)),
        hei=max(0.0, min(100.0, hei_sum / w_sum)),
        gcs=max(0.0, min(100.0, gcs_sum / w_sum)),
        pss=max(0.0, min(100.0, pss_sum / w_sum)),
        acs=acs_val,
    )


def risk_label(
    before: AreaScores,
    after: AreaScores,
) -> RiskInfo | None:
    """Risk label for a Protect building change (PLANNING.md §Risk label).

    The worst change is the largest of: VCI drop, HEI rise, GCS drop, PSS drop.
    <10 → LOW, 10-24 → MODERATE, >=25 → HIGH.
    """
    candidates: list[tuple[float, IndexKey]] = [
        (max(0.0, before.vci - after.vci), "vci"),
        (max(0.0, after.hei - before.hei), "hei"),
        (max(0.0, before.gcs - after.gcs), "gcs"),
        (max(0.0, before.pss - after.pss), "pss"),
    ]
    worst_change, worst_index = max(candidates, key=lambda x: x[0])

    label: RiskLabel
    if worst_change >= S.risk_high_min:
        label = "HIGH"
    elif worst_change >= S.risk_moderate_min:
        label = "MODERATE"
    else:
        label = "LOW"

    return RiskInfo(label=label, index=worst_index, change=worst_change)
