"""The heat check: does the baseline heat index rank blocks the way measured surface temperature does?

docs/PLANNING.md, "Checking the heat index against measurement". Inputs are the committed table of per-block median
Landsat surface temperature (`evals/heat_check/data/<area>_block_lst.csv`, written by `pipeline heat-check`) and the
engine's baseline scores. The statistic is the Spearman rank correlation with average ranks for ties; its p-value is a
two-sided permutation p-value with a fixed seed. There is no pass mark. Nothing here changes the engine or any weight.
"""

import json
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import numpy.typing as npt
import pandas as pd

from .bundle import REPO_ROOT

DATA_DIR = REPO_ROOT / "evals" / "heat_check" / "data"
ENV_DATA_DIR = "ECOZONE_HEAT_CHECK_DATA"
"""Overrides the folder the table is read from; the unit tests point it at a synthetic table."""
PRIMARY = "hei"
SECONDARY = ("vci", "gcs", "pss")
"""Pre-declared before the first run, reported with the primary and labelled secondary. Not corrected for multiple
comparisons; they are context, not a search for the best-looking index."""
SPLITS = ("test", "all", "tune")
PERMUTATIONS = 10_000
SEED = 20261018
MIN_BLOCKS = 3
COMMAND = "uv run --extra ee pipeline heat-check --area {area}"

Floats = npt.NDArray[np.float64]


def data_dir() -> Path:
    return Path(os.environ[ENV_DATA_DIR]) if os.environ.get(ENV_DATA_DIR) else DATA_DIR


def csv_path(area_id: str) -> Path:
    return data_dir() / f"{area_id}_block_lst.csv"


def meta_path(area_id: str) -> Path:
    return data_dir() / f"{area_id}_block_lst.meta.json"


def not_run_message(area_id: str) -> str:
    shown = csv_path(area_id)
    shown = shown.relative_to(REPO_ROOT) if shown.is_relative_to(REPO_ROOT) else shown
    return (
        f"heat check: not run. {shown} does not exist. Create it with "
        f"`{COMMAND.format(area=area_id)}` (needs Earth Engine access; see evals/heat_check/README.md)."
    )


def average_ranks(values: Floats | list[float]) -> Floats:
    """Ranks starting at 1, tied values share the mean of the ranks they span."""
    x = np.asarray(values, dtype=np.float64)
    _, inverse, counts = np.unique(x, return_inverse=True, return_counts=True)
    ends = np.cumsum(counts)
    starts = ends - counts + 1
    return ((starts + ends) / 2.0)[inverse.reshape(-1)]


def _pearson(a: Floats, b: Floats) -> float:
    ac, bc = a - a.mean(), b - b.mean()
    denom = math.sqrt(float(ac @ ac) * float(bc @ bc))
    return float(ac @ bc) / denom if denom > 0 else math.nan


def spearman(x: Floats | list[float], y: Floats | list[float]) -> float:
    """Spearman rank correlation; NaN when either side is constant."""
    return _pearson(average_ranks(x), average_ranks(y))


def permutation_p(
    x: Floats | list[float], y: Floats | list[float], permutations: int = PERMUTATIONS, seed: int = SEED
) -> float:
    """Two-sided permutation p-value of the Spearman correlation: the share of random pairings (the observed one
    included) whose |rho| is at least the observed |rho|."""
    rx, ry = average_ranks(x), average_ranks(y)
    observed = _pearson(rx, ry)
    if math.isnan(observed):
        return math.nan
    rng = np.random.default_rng(seed)
    shuffled = rng.permuted(np.tile(ry, (permutations, 1)), axis=1)
    xc = rx - rx.mean()
    sc = shuffled - shuffled.mean(axis=1, keepdims=True)
    rho = (sc @ xc) / np.sqrt((xc @ xc) * np.einsum("ij,ij->i", sc, sc))
    hits = int(np.sum(np.abs(rho) >= abs(observed) - 1e-12))
    return (1 + hits) / (permutations + 1)


@dataclass(frozen=True)
class Correlation:
    n: int
    rho: float
    p_value: float


def correlate(x: Floats | list[float], y: Floats | list[float]) -> Correlation:
    return Correlation(len(x), spearman(x, y), permutation_p(x, y))


def read_lst(path: Path) -> pd.DataFrame:
    """The committed table: block_id, lst_kelvin, valid_pixels."""
    frame = pd.read_csv(path, dtype={"block_id": str})
    missing = {"block_id", "lst_kelvin", "valid_pixels"} - set(frame.columns)
    if missing:
        raise ValueError(f"{path.name} lacks columns {sorted(missing)}")
    return frame


def join_blocks(lst: pd.DataFrame, baselines: Mapping[str, Any], split: Mapping[str, str]) -> pd.DataFrame:
    """One row per block in the table with its split and the engine's baseline VCI, HEI, GCS and PSS."""
    unknown = sorted(set(lst["block_id"]) - set(baselines))
    if unknown:
        raise ValueError(f"{len(unknown)} blocks in the table are not in the bundle, e.g. {unknown[:3]}")
    rows = [
        {
            "block_id": b,
            "split": split[b],
            "lst": float(k),
            "pixels": float(p),
            **{i: float(getattr(baselines[b], i)) for i in (PRIMARY, *SECONDARY)},
        }
        for b, k, p in zip(lst["block_id"], lst["lst_kelvin"], lst["valid_pixels"], strict=True)
    ]
    return pd.DataFrame(rows)


def subset(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    return frame if name == "all" else cast(pd.DataFrame, frame.loc[frame["split"] == name])


def correlations(frame: pd.DataFrame, index: str) -> dict[str, Correlation]:
    """The index against surface temperature on the test, all and tune blocks."""
    out: dict[str, Correlation] = {}
    for name in SPLITS:
        part = subset(frame, name)
        out[name] = correlate(part[index].to_numpy(dtype=np.float64), part["lst"].to_numpy(dtype=np.float64))
    return out


def provenance(meta: Mapping[str, Any], bundle_meta: Mapping[str, Any]) -> dict[str, Any]:
    """What the report may say about the satellite data: dataset ids, window, scenes, dates. No temperatures."""
    return {
        "datasets": meta["datasets"],
        "windows": meta["windows"],
        "years_used": meta["years_used"],
        "scenes_total": meta["scenes_total"],
        "min_scenes": meta["min_scenes"],
        "min_scenes_met": meta["min_scenes_met"],
        "fetch_date": meta["fetch_date"],
        "earth_engine_project": meta["earth_engine_project"],
        "scale_m": meta["scale_m"],
        "native_thermal_resolution_m": meta["native_thermal_resolution_m"],
        "scene_max_cloud_cover_pct": meta["scene_max_cloud_cover_pct"],
        "st_qa_max_uncertainty_k": meta["st_qa_max_uncertainty_k"],
        "blocks_requested": meta["blocks_requested"],
        "blocks_with_lst": meta["blocks_with_lst"],
        "blocks_dropped": len(meta["blocks_dropped"]),
        "valid_pixels_min": meta["valid_pixels_min"],
        "valid_pixels_median": meta["valid_pixels_median"],
        "valid_pixels_max": meta["valid_pixels_max"],
        "bundle_version_matches": meta.get("bundle_version") == bundle_meta.get("bundle_version"),
        "bundle_settings_hash_matches": meta.get("bundle_settings_hash") == bundle_meta.get("settings_hash"),
    }


def read_meta(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text()))
