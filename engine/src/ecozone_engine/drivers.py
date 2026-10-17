"""Driver tag rules for blocks (PLANNING.md §Primary drivers)."""

from __future__ import annotations

from .settings import SETTINGS


def block_drivers(
    pss: float,
    i_s: float,
    roof_albedo: float,
    d_green: float,
    wait_weight: float,
) -> tuple[str, ...]:
    """Return the sorted driver tags that explain what interventions would help this block.

    Tags are a subset of the Repair drivers from PLANNING.md:
      SHADE_GAIN        — PSS is low; a shade structure or tree row would help
      IMPERVIOUS_LOSS   — high impervious share; depaving or pocket green would help
      ALBEDO_GAIN       — low roof albedo; cool roof coating would help
      GREEN_LINK        — far from existing green or low green buffer; pocket green would help
      WAIT_POINT_COVERED — waiting points nearby worth covering
    """
    tags: list[str] = []
    if pss < SETTINGS.driver_shade_pss_threshold:
        tags.append("SHADE_GAIN")
    if i_s > SETTINGS.driver_impervious_threshold:
        tags.append("IMPERVIOUS_LOSS")
    if roof_albedo < SETTINGS.driver_albedo_threshold:
        tags.append("ALBEDO_GAIN")
    if d_green > SETTINGS.driver_green_link_threshold:
        tags.append("GREEN_LINK")
    if wait_weight > 0.0:
        tags.append("WAIT_POINT_COVERED")
    return tuple(sorted(tags))
