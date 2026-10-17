"""apply_building() for Protect: attribute deltas from a proposed building (PLANNING.md §Protect)."""

from __future__ import annotations

from .errors import InvalidChangeError, UnknownParcelError
from .interventions import BlockDeltas
from .model import AreaModel, Change
from .settings import SETTINGS as S
from .sun import delta_theta_deg


def apply_building(area: AreaModel, change: Change) -> BlockDeltas:
    """Compute attribute deltas for a Protect building change.

    params (sorted by name): floors, footprint_pct, green_pct, orientation_deg.
    Changes H_W, L_built (approximation), V, G_c, I_s, canyon_axis_deg (via orientation).

    Ventilation direction: adding a building never raises the block's VCI. H_W only goes up (the higher of the
    block's and the building's), L_built only goes up, and the canyon axis only moves to a worse alignment with
    the wind. The comments below say why each is needed.

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
    # A proposed building adds to the block's street canyon, it never replaces it with something lower. Setting
    # the block's H/W to the building's own H/W made a 1 or 2 floor building lower H/W and raise O_b, so the
    # block's VCI rose (Deccan pc_017 +2.3 at 1 floor, pc_001 +1.25, pc_010 +0.08). The block keeps the higher
    # of the two.
    new_hw = max(blk.H_W, h_m / w_m)

    # The building's long axis can only worsen the block's wind alignment (W_a), never improve it. Assigning the
    # building's orientation to the whole block's canyon axis let an orientation along the wind raise W_a by as
    # much as a 12 floor building lowered O_b (Deccan pc_017: worst drop 14.3 at orientation 30, 0 at 0, 90 and
    # 135), so a tall building could look harmless just by how it was turned. The block keeps whichever axis is
    # further from the wind: orientation across the wind still lowers VCI, orientation along it simply costs
    # nothing, and the choice of orientation stays a real lever for the design search.
    wind_from_deg = area.wind_from_deg
    keeps_block_axis = delta_theta_deg(orientation_deg, wind_from_deg) <= delta_theta_deg(
        blk.canyon_axis_deg, wind_from_deg
    )
    axis_delta = 0.0 if keeps_block_axis else orientation_deg - blk.canyon_axis_deg

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
            "canyon_axis_deg": axis_delta,
        }
    }
    return deltas
