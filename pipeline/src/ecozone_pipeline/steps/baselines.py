"""Baseline scores by calling the engine; the pipeline never computes an index itself (pipeline/RULES.md)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ecozone_engine import NotImplementedYetError, compute_baselines, load_bundle

from ..store import read_json, write_json


def run(bundle_dir: Path) -> dict[str, Any]:
    """Add `baselines.parquet` and `baseline_area` to a bundle; record the step as skipped until the engine can."""
    meta_path = bundle_dir / "meta.json"
    meta = read_json(meta_path)
    skipped: list[str] = [s for s in meta.get("skipped_steps", []) if s != "baselines"]
    try:
        data = compute_baselines(load_bundle(bundle_dir))
    except NotImplementedYetError as err:
        meta["skipped_steps"] = [*skipped, "baselines"]
        write_json(meta, meta_path)
        return {"skipped": "baselines", "reason": str(err)}

    frame = pd.DataFrame(
        [{"block_id": bid, "vci": s.vci, "hei": s.hei, "gcs": s.gcs, "pss": s.pss} for bid, s in data.blocks]
    ).sort_values("block_id")
    frame.to_parquet(bundle_dir / "baselines.parquet", index=False)
    meta["skipped_steps"] = skipped
    meta["baseline_area"] = {
        "vci": data.area.vci, "hei": data.area.hei, "gcs": data.area.gcs, "pss": data.area.pss, "acs": data.area.acs,
    }  # fmt: skip
    write_json(meta, meta_path)
    return {"blocks": len(frame), "acs": data.area.acs}
