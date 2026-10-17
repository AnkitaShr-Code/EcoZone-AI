"""apply_building() for Protect: attribute deltas from a proposed building (PLANNING.md §Protect)."""

from __future__ import annotations

from .errors import InvalidChangeError, UnknownParcelError
from .interventions import BlockDeltas
from .model import AreaModel, Change
from .settings import SETTINGS as S


def apply_building(area: AreaModel, change: Change) -> BlockDeltas:
    """Compute attribute deltas for a Protect building change.

    params (sorted by name): floors, footprint_pct, green_pct, orientation_deg.
    Changes H_W, L_built (approximation), V, G_c, I_s, canyon_axis_deg (via orientation).

    Note: L_built (longest unbroken built-up run) is approximated here as proportional to
    the parcel footprint fraction, because the exact spatial run requires the full wind-line
    geometry which is not in the bundle. The approximation is conservative for prototype use.
    """
    parcel_id = change.site_id
    parcel = next((p for p in area.parcels if p.parcel_id == parcel_id), None)
    if parcel is None:
        raise UnknownParcelError(parcel_id)

    params = dict(change.params)
    floors = params.get("floors", 0.0)
    footprint_pct = params.get("footprint_pct", 0.0)
    green_pct = params.get("green_pct", 0.0)
    orientation_deg = params.get("orientation_deg", parcel.street_bearing_deg)

    if floors < 0.0 or footprint_pct < 0.0 or footprint_pct > 100.0:
        raise InvalidChangeError(f"Parcel {parcel_id}: floors must be >= 0 and footprint_pct in [0, 100].")

    block_id = parcel.block_id
    blk = next((b for b in area.blocks if b.block_id == block_id), None)
    if blk is None:
        return {}

    import math

    h_m = floors * S.metres_per_floor
    w_m = parcel.road_width_m if parcel.road_width_m > 0.0 else 8.0
    new_hw = h_m / w_m

    # V proxy: floors × footprint_fraction × parcel_area
    new_v = floors * (footprint_pct / 100.0) * parcel.area_m2

    # Approximate L_built increment: footprint fraction × parcel width (side-on to wind)
    parcel_width_approx = math.sqrt(parcel.area_m2 * footprint_pct / 100.0)
    l_built_delta = parcel_width_approx

    # Green share: green_pct of the parcel area that was previously paved
    green_area_m2 = parcel.area_m2 * green_pct / 100.0
    impervious_area_m2 = parcel.area_m2 * (footprint_pct / 100.0)

    area_m2 = blk.area_m2 if blk.area_m2 > 0.0 else 1.0
    gc_delta = min(100.0 - blk.G_c, green_area_m2 / area_m2 * 100.0)
    is_delta = min(blk.I_s, impervious_area_m2 / area_m2 * 100.0)

    deltas: BlockDeltas = {
        block_id: {
            "H_W": new_hw - blk.H_W,
            "V": new_v - blk.V,
            "L_built": l_built_delta,
            "G_c": gc_delta,
            "I_s": is_delta,
            "canyon_axis_deg": orientation_deg - blk.canyon_axis_deg,
        }
    }
    return deltas
