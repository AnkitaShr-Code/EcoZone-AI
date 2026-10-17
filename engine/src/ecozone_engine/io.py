# pyright: reportArgumentType=none, reportReturnType=none, reportGeneralTypeIssues=none, reportIndexIssue=none, reportOperatorIssue=none, reportOptionalMemberAccess=none, reportAttributeAccessIssue=none, reportCallIssue=none, reportUnknownMemberType=none, reportUnknownVariableType=none, reportUnknownArgumentType=none
"""Bundle loading: the only module that touches geopandas or pyarrow (engine/RULES.md).

WP5a dependency: implemented here because WP5a has not merged yet (see PR description).
geopandas ships no type stubs; pyright strictness is relaxed for this file only (same reason as pipeline).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import geopandas as gpd
from shapely import STRtree

from .errors import InvalidBundleError
from .indices import block_cooling, gcs, hei, vci
from .model import (
    AreaModel,
    AreaScores,
    BlockRow,
    BuildingRow,
    ChunkRow,
    ParcelRow,
    Scores,
    ShadeTime,
    SiteRow,
    SunEntry,
    WaitPointRow,
)
from .settings import SETTINGS as S

_SHADE_TIMES: tuple[ShadeTime, ...] = ("13:00", "15:00", "16:00")


def _opt_str(value: object) -> str | None:
    """A text column value, or None for a missing one (None, NaN or the string 'None')."""
    if value is None or (isinstance(value, float) and math.isnan(value)) or str(value) == "None":
        return None
    return str(value)


def load_bundle(path: Path) -> AreaModel:
    """Load one area bundle directory (GeoParquet tables + meta.json) into an immutable AreaModel."""
    meta_path = path / "meta.json"
    with meta_path.open() as f:
        meta: dict[str, object] = json.load(f)

    for _required in ("area_id", "bundle_version"):
        if _required not in meta:
            raise InvalidBundleError(_required, str(path))
    area_id = str(meta["area_id"])
    bundle_version = str(meta["bundle_version"])
    v_ref = float(str(meta.get("V_ref", 0.0)))
    wind_from_deg = float(str(meta.get("wind_from_deg", 270.0)))

    shade_times = tuple(t for t in _SHADE_TIMES if t in meta.get("shade_times", _SHADE_TIMES))

    raw_sun: list[dict[str, object]] = meta.get("sun", [])  # type: ignore[assignment]
    sun_entries: list[SunEntry] = []
    for entry in raw_sun:
        t = str(entry["time"])
        if t in ("13:00", "15:00", "16:00"):
            sun_entries.append(
                SunEntry(
                    time=t,  # type: ignore[arg-type]
                    altitude_deg=float(str(entry["altitude_deg"])),
                    azimuth_deg=float(str(entry["azimuth_deg"])),
                )
            )
    sun_tuple = tuple(sorted(sun_entries, key=lambda s: s.time))

    # ── Load tables ───────────────────────────────────────────────────────────
    blocks_gdf = gpd.read_parquet(path / "blocks.parquet")
    buildings_gdf = gpd.read_parquet(path / "buildings.parquet")
    chunks_gdf = gpd.read_parquet(path / "chunks.parquet")
    sites_gdf = gpd.read_parquet(path / "sites.parquet")
    wait_gdf = gpd.read_parquet(path / "wait_points.parquet")
    parcels_gdf = gpd.read_parquet(path / "parcels.parquet")

    # ── Build row tuples (sorted by id for determinism) ───────────────────────
    block_rows: list[BlockRow] = []
    for _, row in blocks_gdf.sort_values("id").iterrows():
        block_rows.append(
            BlockRow(
                block_id=str(row["id"]),
                geometry=row["geometry"],
                area_m2=float(row["area_m2"]),
                building_count=int(row.get("building_count", 0)),
                coverage=float(row.get("coverage", 0.0)),
                median_footprint_m2=float(row.get("median_footprint_m2", 0.0)),
                median_floors=float(row.get("median_floors", 0.0)),
                built_form=str(row.get("built_form", "other")),
                I_s=float(row.get("I_s", 0.0)),
                G_c=float(row.get("G_c", 0.0)),
                G_buf=float(row.get("G_buf", 0.0)),
                d_green=float(row.get("d_green", 1000.0)),
                d_water=float(row.get("d_water", 1000.0)),
                H_W=float(row.get("H_W", 0.0)),
                canyon_axis_deg=float(row.get("canyon_axis_deg", 0.0)),
                L_built=float(row.get("L_built", 0.0)),
                V=float(row.get("V", 0.0)),
                roof_albedo=float(row.get("roof_albedo", 0.25)),
            )
        )

    building_rows: list[BuildingRow] = []
    for _, row in buildings_gdf.sort_values("id").iterrows():
        building_rows.append(
            BuildingRow(
                building_id=str(row["id"]),
                geometry=row["geometry"],
                height_m=float(row.get("height_m", 0.0)),
                block_id=str(row.get("block_id", "")),
                height_source=str(row.get("height_source", "typology")),
            )
        )

    chunk_rows: list[ChunkRow] = []
    for _, row in chunks_gdf.sort_values("id").iterrows():
        chunk_rows.append(
            ChunkRow(
                chunk_id=str(row["id"]),
                geometry=row["geometry"],
                block_id=str(row.get("block_id", "")),
                length_m=float(row.get("length_m", 10.0)),
                near_wait=bool(row.get("near_wait", False)),
                road_name=_opt_str(row.get("road_name")),
                road_class=str(row.get("road_class", "")),
            )
        )

    site_rows: list[SiteRow] = []
    for _, row in sites_gdf.sort_values("id").iterrows():
        hw_raw = row.get("H_W")
        hw_is_nan = isinstance(hw_raw, float) and math.isnan(hw_raw)
        hw_val: float | None = float(hw_raw) if hw_raw is not None and not hw_is_nan else None
        block_id_raw = row.get("block_id")
        block_id_val: str | None = (
            str(block_id_raw) if block_id_raw is not None and str(block_id_raw) != "None" else None
        )
        wait_id_raw = row.get("wait_point_id")
        wait_id_val: str | None = _opt_str(wait_id_raw)
        site_rows.append(
            SiteRow(
                site_id=str(row["id"]),
                kind=str(row.get("kind", "")),
                geometry=row["geometry"],
                block_id=block_id_val,
                quantity_min=float(row.get("quantity_min", 1.0)),
                quantity_max=float(row.get("quantity_max", 1.0)),
                rule=str(row.get("rule", "")),
                rejected=bool(row.get("rejected", False)),
                wait_point_id=wait_id_val,
                H_W=hw_val,
                time_to_benefit=str(row.get("time_to_benefit", "years")),
                name=str(row.get("name", "")),
            )
        )

    wait_rows: list[WaitPointRow] = []
    for _, row in wait_gdf.sort_values("id").iterrows():
        wait_rows.append(
            WaitPointRow(
                wait_id=str(row["id"]),
                geometry=row["geometry"],
                kind=str(row.get("kind", "")),
                weight=float(row.get("weight", 1.0)),
                name=_opt_str(row.get("name")),
            )
        )

    parcel_rows: list[ParcelRow] = []
    for _, row in parcels_gdf.sort_values("id").iterrows():
        parcel_rows.append(
            ParcelRow(
                parcel_id=str(row["id"]),
                block_id=str(row.get("block_id", "")),
                area_m2=float(row.get("area_m2", 0.0)),
                road_width_m=float(row.get("road_width_m", 8.0)),
                street_bearing_deg=float(row.get("street_bearing_deg", 0.0)),
                neighbour_height_m=float(row.get("neighbour_height_m", 0.0)),
                geometry=row["geometry"],
                name=str(row.get("name", "")),
                road_name=_opt_str(row.get("road_name")),
            )
        )

    # ── Build STRtrees ────────────────────────────────────────────────────────
    block_tree = STRtree([b.geometry for b in block_rows])
    building_tree = STRtree([b.geometry for b in building_rows])
    chunk_tree = STRtree([c.geometry for c in chunk_rows])

    # ── Compute baseline scores ───────────────────────────────────────────────
    from .shade import area_pss, block_pss, compute_chunk_shading
    from .shadows import building_shadows_at

    building_shadows = tuple((s.time, tuple(building_shadows_at(building_rows, s))) for s in sun_tuple)
    chunk_shading = compute_chunk_shading(
        AreaModel(
            area_id=area_id,
            bundle_version=bundle_version,
            V_ref=v_ref,
            wind_from_deg=wind_from_deg,
            sun=sun_tuple,
            blocks=tuple(block_rows),
            buildings=tuple(building_rows),
            chunks=tuple(chunk_rows),
            sites=tuple(site_rows),
            wait_points=tuple(wait_rows),
            parcels=tuple(parcel_rows),
            baseline_building_shadows=building_shadows,
        )
    )

    block_baselines: list[tuple[str, Scores]] = []
    vci_sum = 0.0
    hei_sum = 0.0
    gcs_sum = 0.0
    pss_sum = 0.0
    weight_sum = 0.0

    chunk_list = list(chunk_rows)
    for b in sorted(block_rows, key=lambda r: r.block_id):
        b_vci = vci(
            h_w=b.H_W,
            canyon_axis_deg=b.canyon_axis_deg,
            l_built=b.L_built,
            d_water=b.d_water,
            wind_from_deg=wind_from_deg,
        )
        b_hei = hei(i_s=b.I_s, g_c=b.G_c, v=b.V, v_ref=v_ref, roof_albedo=b.roof_albedo)
        b_gcs = gcs(g_buf=b.G_buf, d_green=b.d_green)
        b_pss = block_pss(b.block_id, chunk_list, chunk_shading)
        scores = Scores(vci=b_vci, hei=b_hei, gcs=b_gcs, pss=b_pss)
        block_baselines.append((b.block_id, scores))

        # Weighted for area ACS
        from .priority import vulnerability, wait_weight

        ew = wait_weight(b, list(wait_rows))
        vv = vulnerability(b)
        w = ew * vv
        cooling = block_cooling(b_hei, b_pss, b_gcs)
        vci_sum += w * b_vci
        hei_sum += w * b_hei
        gcs_sum += w * b_gcs
        pss_sum += w * b_pss
        weight_sum += w

    a_pss = area_pss(chunk_list, chunk_shading)
    if weight_sum > 0.0:
        a_vci = vci_sum / weight_sum
        a_hei = hei_sum / weight_sum
        a_gcs = gcs_sum / weight_sum
    else:
        a_vci = a_hei = a_gcs = 0.0

    # ACS = weighted mean of block cooling scores
    acs_sum = 0.0
    w2_sum = 0.0
    bbaseline_dict = dict(block_baselines)
    for b in sorted(block_rows, key=lambda r: r.block_id):
        from .priority import vulnerability, wait_weight

        ew = wait_weight(b, list(wait_rows))
        vv = vulnerability(b)
        w = ew * vv
        sc = bbaseline_dict[b.block_id]
        cooling = block_cooling(sc.hei, sc.pss, sc.gcs)
        acs_sum += w * cooling
        w2_sum += w

    area_acs = acs_sum / w2_sum if w2_sum > 0.0 else 0.0
    area_baseline = AreaScores(
        vci=max(0.0, min(100.0, a_vci)),
        hei=max(0.0, min(100.0, a_hei)),
        gcs=max(0.0, min(100.0, a_gcs)),
        pss=max(0.0, min(100.0, a_pss)),
        acs=max(0.0, min(100.0, area_acs)),
    )

    # Meta facts for summary(); a bundle without them falls back to what the tables or settings give.
    raw_bbox = meta.get("bbox_xy")
    bbox_xy: tuple[float, float, float, float]
    if isinstance(raw_bbox, list) and len(raw_bbox) == 4:
        bbox_xy = (float(raw_bbox[0]), float(raw_bbox[1]), float(raw_bbox[2]), float(raw_bbox[3]))
    else:
        minx, miny, maxx, maxy = blocks_gdf.total_bounds
        bbox_xy = (float(minx), float(miny), float(maxx), float(maxy))
    skipped = meta.get("skipped_steps", [])
    footpath_derived = meta.get("derived_footpath_chunks", 0)

    return AreaModel(
        area_id=area_id,
        bundle_version=bundle_version,
        V_ref=v_ref,
        wind_from_deg=wind_from_deg,
        name=str(meta.get("name", area_id)),
        city=str(meta.get("city", "")),
        bbox_xy=bbox_xy,
        reference_date=str(meta.get("reference_date", "")),
        shade_times=shade_times,
        metres_per_floor=float(str(meta.get("metres_per_floor", S.metres_per_floor))),
        derived_footpath_chunks=int(str(footpath_derived)),
        skipped_steps=tuple(str(x) for x in skipped) if isinstance(skipped, list) else (),
        attribution=str(meta.get("attribution", "")),
        sun=sun_tuple,
        blocks=tuple(block_rows),
        buildings=tuple(building_rows),
        chunks=tuple(chunk_rows),
        sites=tuple(site_rows),
        wait_points=tuple(wait_rows),
        parcels=tuple(parcel_rows),
        block_baselines=tuple(sorted(block_baselines, key=lambda x: x[0])),
        area_baseline=area_baseline,
        baseline_building_shadows=building_shadows,
        baseline_shading=tuple(sorted(chunk_shading.items())),
        block_tree=block_tree,
        building_tree=building_tree,
        chunk_tree=chunk_tree,
    )
