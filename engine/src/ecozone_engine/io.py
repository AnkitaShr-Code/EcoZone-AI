# pyright: reportArgumentType=none, reportReturnType=none, reportGeneralTypeIssues=none, reportIndexIssue=none, reportOperatorIssue=none, reportOptionalMemberAccess=none, reportAttributeAccessIssue=none, reportCallIssue=none, reportUnknownMemberType=none, reportUnknownVariableType=none, reportUnknownArgumentType=none, reportMissingTypeStubs=none
"""Bundle loading: the only module that touches geopandas or pyarrow (engine/RULES.md).

geopandas ships no type stubs; pyright strictness is relaxed for this file only (same reason as pipeline).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import cast

import geopandas as gpd
import pandas as pd
from shapely.strtree import STRtree

from .drivers import block_drivers
from .indices import gcs as _gcs
from .indices import hei as _hei
from .indices import vci as _vci
from .model import (
    AreaMeta,
    AreaModel,
    AreaScores,
    BaselineData,
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
from .priority import (
    acs as _acs,
)
from .priority import (
    area_gcs,
    area_hei,
    area_vci,
    priority,
    priority_classes,
)
from .shade import block_pss, chunk_pss, compute_chunk_shade


def load_bundle(path: Path) -> AreaModel:
    """Load one area bundle directory (GeoParquet tables + meta.json) into an immutable AreaModel."""
    path = Path(path)
    if not path.is_dir():
        raise FileNotFoundError(f"Bundle directory not found: {path}")

    # ------------------------------------------------------------------ meta
    raw = json.loads((path / "meta.json").read_text())
    shade_times: tuple[ShadeTime, ...] = tuple(cast("ShadeTime", e["time"]) for e in raw["sun"])
    sun_entries = tuple(
        SunEntry(
            time=cast("ShadeTime", e["time"]),
            altitude_deg=e["altitude_deg"],
            azimuth_deg=e["azimuth_deg"],
        )
        for e in raw["sun"]
    )
    meta = AreaMeta(
        area_id=raw.get("area_id", path.name),
        name=raw.get("name", ""),
        city=raw.get("city", ""),
        bundle_version=raw.get("bundle_version", "v1"),
        bbox_xy=tuple(raw["bbox_xy"]),  # type: ignore[arg-type]
        reference_date=raw.get("reference_date", ""),
        shade_times=shade_times,
        sun=sun_entries,
        wind_from_deg=raw.get("wind_from_deg", 0.0),
        v_ref=raw.get("V_ref", 1.0),
        attribution=raw.get("attribution", ""),
        counts=MappingProxyType(raw.get("counts", {})),
        buildings_by_height_source=MappingProxyType(raw.get("buildings_by_height_source", {})),
        derived_footpath_chunks=raw.get("derived_footpath_chunks", 0),
        skipped_steps=tuple(raw.get("skipped_steps", [])),
        metres_per_floor=raw.get("metres_per_floor", 3.0),
    )

    # --------------------------------------------------------------- buildings
    bdf = gpd.read_parquet(path / "buildings.parquet")
    buildings = tuple(
        BuildingRow(
            building_id=str(row["id"]),
            geometry=row["geometry"],
            height_m=float(row["height_m"]),
            block_id=str(row["block_id"]),
            roof_albedo=float(row["roof_albedo"]),
            height_source=str(row["height_source"]),
        )
        for _, row in bdf.sort_values("id").iterrows()
    )

    # ----------------------------------------------------------------- chunks
    cdf = gpd.read_parquet(path / "chunks.parquet")
    # Compute shade flags per chunk (sorted by id for determinism)
    cdf_sorted = cdf.sort_values("id")
    raw_chunks_unsorted = [
        ChunkRow(
            chunk_id=str(row["id"]),
            geometry=row["geometry"],
            block_id=str(row["block_id"]),
            length_m=float(row["length_m"]),
            near_wait=bool(row["near_wait"]),
            bearing_deg=float(row["bearing_deg"]),
            road_class=str(row["road_class"]),
        )
        for _, row in cdf_sorted.iterrows()
    ]
    shade_by_id = compute_chunk_shade(raw_chunks_unsorted, buildings, sun_entries)
    chunks = tuple(
        ChunkRow(
            chunk_id=c.chunk_id,
            geometry=c.geometry,
            block_id=c.block_id,
            length_m=c.length_m,
            near_wait=c.near_wait,
            bearing_deg=c.bearing_deg,
            road_class=c.road_class,
            shade=shade_by_id[c.chunk_id],
            pss=chunk_pss(shade_by_id[c.chunk_id]),
        )
        for c in raw_chunks_unsorted
    )
    chunk_index: dict[str, int] = {c.chunk_id: i for i, c in enumerate(chunks)}

    # Compute block PSS: group chunks by block_id
    chunks_by_block: dict[str, list[ChunkRow]] = {}
    for c in chunks:
        chunks_by_block.setdefault(c.block_id, []).append(c)

    # --------------------------------------------------------------- blocks
    blk_df = gpd.read_parquet(path / "blocks.parquet")
    blk_df_sorted = blk_df.sort_values("id")
    # First pass: compute vci, hei, gcs, pss (without priority – need all blocks for classes)
    raw_blocks: list[BlockRow] = []
    for _, row in blk_df_sorted.iterrows():
        bid = str(row["id"])
        blk_chunks = chunks_by_block.get(bid, [])
        blk_pss = block_pss(blk_chunks)
        b_vci = _vci(
            canyon_axis_deg=float(row["canyon_axis_deg"]),
            wind_from_deg=meta.wind_from_deg,
            l_built=float(row["L_built"]),
            h_w=float(row["H_W"]),
            d_water=float(row["d_water"]),
        )
        b_hei = _hei(
            i_s=float(row["I_s"]),
            g_c=float(row["G_c"]),
            v=float(row["V"]),
            v_ref=meta.v_ref,
            roof_albedo=float(row["roof_albedo"]),
        )
        b_gcs = _gcs(
            g_buf=float(row["G_buf"]),
            d_green=float(row["d_green"]),
        )
        raw_blocks.append(
            BlockRow(
                block_id=bid,
                area_m2=float(row["area_m2"]),
                geometry=row["geometry"],
                i_s=float(row["I_s"]),
                g_c=float(row["G_c"]),
                g_buf=float(row["G_buf"]),
                d_green=float(row["d_green"]),
                d_water=float(row["d_water"]),
                h_w=float(row["H_W"]),
                canyon_axis_deg=float(row["canyon_axis_deg"]),
                l_built=float(row["L_built"]),
                v=float(row["V"]),
                roof_albedo=float(row["roof_albedo"]),
                wait_weight=float(row["wait_weight"]),
                built_form=str(row["built_form"]),
                coverage=float(row["coverage"]),
                median_footprint_m2=float(row["median_footprint_m2"]),
                median_floors=float(row["median_floors"]),
                vci=b_vci,
                hei=b_hei,
                gcs=b_gcs,
                pss=blk_pss,
                priority=priority(b_hei, blk_pss, float(row["wait_weight"]), str(row["built_form"])),
            )
        )

    # Second pass: assign priority classes (requires all priorities to be known)
    pclasses = priority_classes(raw_blocks)
    blocks = tuple(
        BlockRow(
            block_id=b.block_id,
            area_m2=b.area_m2,
            geometry=b.geometry,
            i_s=b.i_s,
            g_c=b.g_c,
            g_buf=b.g_buf,
            d_green=b.d_green,
            d_water=b.d_water,
            h_w=b.h_w,
            canyon_axis_deg=b.canyon_axis_deg,
            l_built=b.l_built,
            v=b.v,
            roof_albedo=b.roof_albedo,
            wait_weight=b.wait_weight,
            built_form=b.built_form,
            coverage=b.coverage,
            median_footprint_m2=b.median_footprint_m2,
            median_floors=b.median_floors,
            vci=b.vci,
            hei=b.hei,
            gcs=b.gcs,
            pss=b.pss,
            priority=b.priority,
            priority_class=pclasses.get(b.block_id, "medium"),
            drivers=block_drivers(b.pss, b.i_s, b.roof_albedo, b.d_green, b.wait_weight),
        )
        for b in raw_blocks
    )
    block_index: dict[str, int] = {b.block_id: i for i, b in enumerate(blocks)}

    # ------------------------------------------------------------------ sites
    sdf = gpd.read_parquet(path / "sites.parquet")
    sites = tuple(
        SiteRow(
            site_id=str(row["id"]),
            kind=str(row["kind"]),  # type: ignore[arg-type]
            name=str(row["name"]),
            geometry=row["geometry"],
            quantity_min=float(row["quantity_min"]),
            quantity_max=float(row["quantity_max"]),
            rejected=bool(row["rejected"]),
            rule=str(row.get("rule", "")),
            wait_point_id=(str(row["wait_point_id"]) if pd.notna(row["wait_point_id"]) else None),
            h_w=float(row["H_W"]) if pd.notna(row["H_W"]) else 0.0,
            block_id=str(row["block_id"]),
            time_to_benefit=str(row["time_to_benefit"]),
        )
        for _, row in sdf.sort_values("id").iterrows()
    )
    site_index: dict[str, int] = {s.site_id: i for i, s in enumerate(sites)}

    # ----------------------------------------------------------- wait_points
    wpdf = gpd.read_parquet(path / "wait_points.parquet")
    wait_points = tuple(
        WaitPointRow(
            wait_id=str(row["id"]),
            kind=str(row["kind"]),
            name=str(row["name"]),
            weight=float(row["weight"]),
            geometry=row["geometry"],
        )
        for _, row in wpdf.sort_values("id").iterrows()
    )

    # ---------------------------------------------------------------- parcels
    pcldf = gpd.read_parquet(path / "parcels.parquet")
    parcels = tuple(
        ParcelRow(
            parcel_id=str(row["id"]),
            block_id=str(row["block_id"]),
            area_m2=float(row["area_m2"]),
            road_name=(str(row["road_name"]) if pd.notna(row["road_name"]) else None),
            road_width_m=float(row["road_width_m"]),
            street_bearing_deg=float(row["street_bearing_deg"]),
            neighbour_height_m=float(row["neighbour_height_m"]),
            name=str(row["name"]),
            geometry=row["geometry"],
        )
        for _, row in pcldf.sort_values("id").iterrows()
    )
    parcel_index: dict[str, int] = {p.parcel_id: i for i, p in enumerate(parcels)}

    # ---------------------------------------------------------- spatial trees
    building_tree = STRtree([b.geometry for b in buildings])
    chunk_tree = STRtree([c.geometry for c in chunks])

    # ------------------------------------------------------- precompute baseline
    baseline_blocks = tuple((b.block_id, Scores(vci=b.vci, hei=b.hei, gcs=b.gcs, pss=b.pss)) for b in blocks)
    area_acs = _acs(blocks)
    area_avg_vci = area_vci(blocks)
    area_avg_hei = area_hei(blocks)
    area_avg_gcs = area_gcs(blocks)
    area_avg_pss = block_pss(chunks)
    baseline = BaselineData(
        blocks=baseline_blocks,
        area=AreaScores(
            vci=area_avg_vci,
            hei=area_avg_hei,
            gcs=area_avg_gcs,
            pss=area_avg_pss,
            acs=area_acs,
        ),
    )

    return AreaModel(
        area_id=meta.area_id,
        bundle_version=meta.bundle_version,
        meta=meta,
        blocks=blocks,
        chunks=chunks,
        buildings=buildings,
        sites=sites,
        wait_points=wait_points,
        parcels=parcels,
        block_index=MappingProxyType(block_index),
        chunk_index=MappingProxyType(chunk_index),
        site_index=MappingProxyType(site_index),
        parcel_index=MappingProxyType(parcel_index),
        building_tree=building_tree,
        chunk_tree=chunk_tree,
        baseline=baseline,
    )
