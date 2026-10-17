"""Driver tag rules (docs/PLANNING.md §Grounding rules).

Driver tags name what the engine measured, not what Gemini inferred.
Repair tags: SHADE_GAIN, IMPERVIOUS_LOSS, ALBEDO_GAIN, GREEN_LINK, CANOPY_OBSTRUCTION, WAIT_POINT_COVERED.
Protect tags: OBSTRUCTION, BUILT_RUN, IMPERVIOUS_GAIN, MASS_GAIN, GREEN_ISOLATED, SHADE_LOSS.
"""

from __future__ import annotations

from collections.abc import Sequence

from .model import AreaScores, Change
from .settings import SETTINGS as S


def block_drivers(
    *,
    pss: float,
    i_s: float,
    roof_albedo: float,
    d_green: float,
    wait_weight_sum: float,
) -> tuple[str, ...]:
    """Improvement-opportunity driver tags for one block (PLANNING.md §Primary drivers).

    Tags explain what interventions would help.  Unlike repair_drivers (which reflects a
    scored change set), these are derived from the block's baseline attributes alone.
    """
    tags: list[str] = []
    if pss < S.driver_shade_pss_threshold:
        tags.append("SHADE_GAIN")
    if i_s > S.driver_impervious_threshold:
        tags.append("IMPERVIOUS_LOSS")
    if roof_albedo < S.driver_albedo_threshold:
        tags.append("ALBEDO_GAIN")
    if d_green > S.driver_green_link_threshold:
        tags.append("GREEN_LINK")
    if wait_weight_sum > 0.0:
        tags.append("WAIT_POINT_COVERED")
    return tuple(sorted(tags))


def repair_drivers(
    changes: Sequence[Change],
    before: AreaScores,
    after: AreaScores,
    wait_points_covered: int,
) -> tuple[str, ...]:
    """Compute Repair driver tags from the change set and score deltas."""
    tags: list[str] = []

    kinds = {c.kind for c in changes}

    pss_delta = after.pss - before.pss
    if pss_delta > 0.0:
        tags.append("SHADE_GAIN")

    if "depave" in kinds:
        tags.append("IMPERVIOUS_LOSS")

    if "cool_roof" in kinds:
        tags.append("ALBEDO_GAIN")

    gcs_delta = after.gcs - before.gcs
    if gcs_delta > 0.0 and any(k in kinds for k in ("pocket_green", "depave", "tree_row")):
        tags.append("GREEN_LINK")

    if wait_points_covered > 0:
        tags.append("WAIT_POINT_COVERED")

    return tuple(sorted(set(tags)))


def protect_drivers(before: AreaScores, after: AreaScores) -> tuple[str, ...]:
    """Compute Protect driver tags from score deltas."""
    tags: list[str] = []

    vci_drop = before.vci - after.vci
    if vci_drop >= 5.0:
        tags.append("OBSTRUCTION")

    hei_rise = after.hei - before.hei
    if hei_rise > 0.0:
        tags.append("IMPERVIOUS_GAIN")
        tags.append("MASS_GAIN")

    gcs_drop = before.gcs - after.gcs
    if gcs_drop > 0.0:
        tags.append("GREEN_ISOLATED")

    pss_drop = before.pss - after.pss
    if pss_drop > 0.0:
        tags.append("SHADE_LOSS")

    return tuple(sorted(set(tags)))
