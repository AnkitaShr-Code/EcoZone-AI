"""The one scoring path for every change set (docs/ENGINEERING_RULES.md principle 3).

Every index, delta and ACS value is produced by this function. No other code path
may compute a score (CLAUDE.md §Hard rules, principle 2).
"""

from __future__ import annotations

from collections.abc import Sequence

from .building import apply_building
from .costs import portfolio_costs
from .drivers import protect_drivers, repair_drivers
from .errors import InvalidChangeError, UnknownSiteError
from .indices import gcs, hei, vci
from .interventions import collect_deltas
from .model import (
    AreaModel,
    AreaResultData,
    BlockResult,
    BlockRow,
    Change,
    RiskInfo,
    Scores,
    ShadeByTime,
    UnitCosts,
)
from .priority import area_weighted_scores, risk_label
from .settings import SETTINGS as S
from .shade import area_pss, block_pss, compute_chunk_shading


def _validate(area: AreaModel, change: Change) -> None:
    """Raise EngineInputError for invalid changes before any computation."""
    if change.kind == "building":
        if not any(p.parcel_id == change.site_id for p in area.parcels):
            from .errors import UnknownParcelError

            raise UnknownParcelError(change.site_id)
        return

    site = next((s for s in area.sites if s.site_id == change.site_id), None)
    if site is None:
        raise UnknownSiteError(change.site_id)

    # Tree rows must pass the canopy site rule
    if change.kind == "tree_row" and site.rejected:
        raise InvalidChangeError(
            f"Site {change.site_id} was rejected by the canopy site rule ({site.rule}). "
            "Use a shade structure on deep canyons."
        )

    # Quantity range check
    if change.quantity < site.quantity_min or change.quantity > site.quantity_max:
        from .errors import QuantityOutOfRangeError

        raise QuantityOutOfRangeError(change.site_id, change.quantity, site.quantity_min, site.quantity_max)


def _apply_deltas_to_block(block: BlockRow, deltas: dict[str, float]) -> BlockRow:
    """Return a new BlockRow with deltas applied (engine/RULES.md, 'Pure')."""
    return BlockRow(
        block_id=block.block_id,
        geometry=block.geometry,
        area_m2=block.area_m2,
        building_count=block.building_count,
        coverage=block.coverage,
        median_footprint_m2=block.median_footprint_m2,
        median_floors=block.median_floors,
        built_form=block.built_form,
        I_s=max(0.0, min(100.0, block.I_s + deltas.get("I_s", 0.0))),
        G_c=max(0.0, min(100.0, block.G_c + deltas.get("G_c", 0.0))),
        G_buf=max(0.0, min(100.0, block.G_buf + deltas.get("G_buf", 0.0))),
        d_green=max(0.0, block.d_green + deltas.get("d_green", 0.0)),
        d_water=block.d_water,
        H_W=max(0.0, block.H_W + deltas.get("H_W", 0.0)),
        canyon_axis_deg=(block.canyon_axis_deg + deltas.get("canyon_axis_deg", 0.0)) % 360.0,
        L_built=max(0.0, block.L_built + deltas.get("L_built", 0.0)),
        V=max(0.0, block.V + deltas.get("V", 0.0)),
        roof_albedo=max(0.0, min(1.0, block.roof_albedo + deltas.get("roof_albedo", 0.0))),
    )


def rescore(area: AreaModel, changes: Sequence[Change], unit_costs: UnitCosts) -> AreaResultData:
    """Apply a change set and recompute only what it touches. Never mutates `area`.

    All changes go through this single code path (CLAUDE.md §Hard rules, principle 2).
    Iteration order is deterministic: changes and blocks are processed in sorted id order.
    """
    changes_list = list(changes)

    # ── 1. Validate all changes before any scoring ────────────────────────────
    for change in sorted(changes_list, key=lambda c: c.site_id):
        _validate(area, change)

    # ── 2. Collect attribute deltas from interventions ────────────────────────
    repair_changes = [c for c in changes_list if c.kind != "building"]
    building_changes = [c for c in changes_list if c.kind == "building"]

    combined_deltas = collect_deltas(area, repair_changes)

    for change in sorted(building_changes, key=lambda c: c.site_id):
        b_deltas = apply_building(area, change)
        for block_id, attrs in b_deltas.items():
            combined_deltas.setdefault(block_id, {})
            for attr, delta in attrs.items():
                combined_deltas[block_id][attr] = combined_deltas[block_id].get(attr, 0.0) + delta

    # ── 3. Build updated block list ───────────────────────────────────────────
    updated_blocks: list[BlockRow] = []
    for b in sorted(area.blocks, key=lambda r: r.block_id):
        deltas = combined_deltas.get(b.block_id)
        if deltas:
            updated_blocks.append(_apply_deltas_to_block(b, deltas))
        else:
            updated_blocks.append(b)

    # ── 4. Compute new chunk shading with change set applied ──────────────────
    # Create a temporary AreaModel with updated buildings for shadow computation
    from .model import AreaModel

    tmp_area = AreaModel(
        area_id=area.area_id,
        bundle_version=area.bundle_version,
        V_ref=area.V_ref,
        wind_from_deg=area.wind_from_deg,
        sun=area.sun,
        blocks=tuple(updated_blocks),
        buildings=area.buildings,
        chunks=area.chunks,
        sites=area.sites,
        wait_points=area.wait_points,
        parcels=area.parcels,
    )
    new_chunk_shading = compute_chunk_shading(tmp_area, changes_list)

    # ── 5. Baseline chunk shading (already stored, or recompute) ─────────────
    base_chunk_shading = compute_chunk_shading(area)

    # ── 6. Compute before/after scores per block ──────────────────────────────
    baseline_dict = dict(area.block_baselines)
    wait_list = list(area.wait_points)
    chunk_list = list(area.chunks)

    before_scores: dict[str, Scores] = {}
    after_scores: dict[str, Scores] = {}
    block_results: list[BlockResult] = []

    for orig_blk, new_blk in zip(
        sorted(area.blocks, key=lambda r: r.block_id),
        sorted(updated_blocks, key=lambda r: r.block_id),
        strict=False,
    ):
        bid = orig_blk.block_id

        # Before: use stored baseline
        before = baseline_dict.get(bid, Scores(vci=0.0, hei=0.0, gcs=0.0, pss=0.0))
        before_scores[bid] = before

        # After: recompute from updated attributes
        a_vci = vci(
            h_w=new_blk.H_W,
            canyon_axis_deg=new_blk.canyon_axis_deg,
            l_built=new_blk.L_built,
            d_water=new_blk.d_water,
            wind_from_deg=area.wind_from_deg,
        )
        a_hei = hei(
            i_s=new_blk.I_s,
            g_c=new_blk.G_c,
            v=new_blk.V,
            v_ref=area.V_ref,
            roof_albedo=new_blk.roof_albedo,
        )
        a_gcs = gcs(g_buf=new_blk.G_buf, d_green=new_blk.d_green)
        a_pss = block_pss(bid, chunk_list, new_chunk_shading)
        after = Scores(vci=a_vci, hei=a_hei, gcs=a_gcs, pss=a_pss)
        after_scores[bid] = after

        block_results.append(BlockResult(block_id=bid, before=before, after=after))

    # ── 7. Area-level before / after ──────────────────────────────────────────
    area_before = area.area_baseline
    area_after = area_weighted_scores(updated_blocks, after_scores, wait_list, area_pss(chunk_list, new_chunk_shading))

    # ── 8. Ventilation check (PLANNING.md §ACS; engine/RULES.md §Ventilation) ─
    worst_vci_drop = 0.0
    for bid, bafter in sorted(after_scores.items()):
        bbefore = before_scores.get(bid, Scores(vci=0.0, hei=0.0, gcs=0.0, pss=0.0))
        drop = bbefore.vci - bafter.vci
        if drop > worst_vci_drop:
            worst_vci_drop = drop
    ventilation_ok = worst_vci_drop < S.vci_drop_threshold

    # ── 9. Changed chunks ─────────────────────────────────────────────────────
    changed_chunks: list[tuple[str, ShadeByTime]] = []
    for chunk in sorted(area.chunks, key=lambda c: c.chunk_id):
        cid = chunk.chunk_id
        old_state = base_chunk_shading.get(cid, (False, False, False))
        new_state = new_chunk_shading.get(cid, (False, False, False))
        if old_state != new_state:
            changed_chunks.append((cid, new_state))

    # ── 10. Cost ──────────────────────────────────────────────────────────────
    total_cost, quick_win_cost = portfolio_costs(area, changes_list, unit_costs)

    # ── 11. Wait points covered ───────────────────────────────────────────────
    covered_wait_ids: set[str] = set()
    for change in sorted(changes_list, key=lambda c: c.site_id):
        if change.kind == "shade":
            site = next((s for s in area.sites if s.site_id == change.site_id), None)
            if site is not None and site.wait_point_id is not None:
                covered_wait_ids.add(site.wait_point_id)
    wait_points_covered = len(covered_wait_ids)

    # ── 12. Blocks worse ──────────────────────────────────────────────────────
    blocks_worse = sum(
        1
        for bid in sorted(after_scores)
        if (
            after_scores[bid].vci < before_scores.get(bid, after_scores[bid]).vci
            or after_scores[bid].hei > before_scores.get(bid, after_scores[bid]).hei
            or after_scores[bid].gcs < before_scores.get(bid, after_scores[bid]).gcs
        )
    )

    # ── 13. Drivers ───────────────────────────────────────────────────────────
    has_building = bool(building_changes)
    if has_building:
        drivers = protect_drivers(area_before, area_after)
    else:
        drivers = repair_drivers(changes_list, area_before, area_after, wait_points_covered)

    # ── 14. Risk info (Protect only) ──────────────────────────────────────────
    r_info: RiskInfo | None = risk_label(area_before, area_after) if has_building else None

    return AreaResultData(
        before=area_before,
        after=area_after,
        blocks=tuple(block_results),
        chunks=tuple(changed_chunks),
        ventilation_ok=ventilation_ok,
        worst_vci_drop=worst_vci_drop,
        wait_points_covered=wait_points_covered,
        cost_inr=total_cost,
        quick_win_cost_inr=quick_win_cost,
        drivers=drivers,
        blocks_worse=blocks_worse,
        risk=r_info,
    )
