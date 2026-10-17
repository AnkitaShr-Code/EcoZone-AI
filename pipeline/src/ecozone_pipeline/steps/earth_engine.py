"""Earth Engine: median Landsat land surface temperature per block, for the heat check (evals/heat_check/README.md).

This is validation only. It never changes the bundle, is not part of `pipeline all`, and `earthengine-api` is an
optional dependency (`uv run --extra ee ...`), imported lazily in `load_ee`. Importing this module never imports `ee`.

What is computed (docs/PLANNING.md, "Checking the heat index against measurement"):

- Landsat 8 and 9 Collection 2 Level 2, band `ST_B10`; kelvin = DN x 0.00341802 + 149.0.
- Pixels masked where `QA_PIXEL` flags dilated cloud, cirrus, cloud or cloud shadow, where `ST_B10` is fill (0), or
  where `ST_QA` (the per-pixel surface temperature uncertainty, 0.01 K per count) is negative (fill) or above
  `max_st_uncertainty_k`. USGS publishes the band and its scale but no pass value, so that limit is our own screening
  choice, fixed here before any run and not tuned.
- Scenes: March 1 to May 31 of the reference year, scenes whose scene-level `CLOUD_COVER` is under
  `max_cloud_cover`. If fewer than `min_scenes` remain, the same window of the year before is added and
  both years are recorded.
- A per-pixel median composite, then the median of that composite over each block polygon at 30 m. Landsat thermal
  is collected at 100 m and resampled to 30 m, so a block of only a few pixels is a mixed measurement; each block's
  valid pixel count is recorded and blocks with none are dropped.

The Earth Engine client is injected through the `LstBackend` protocol; `EeBackend` is the real one and takes the `ee`
module as an argument so tests can pass a fake.
"""

from __future__ import annotations

import importlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import geopandas as gpd
import pandas as pd
import shapely

from ..config import AreaConfig, Paths
from ..store import read_json, read_table, write_json

DEFAULT_PROJECT = "ecozone-ai-2026"
ENV_PROJECT = "ECOZONE_EE_PROJECT"
ENV_TOKEN = "ECOZONE_EE_ACCESS_TOKEN"
EE_SCOPES = (
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/cloud-platform",
)

DATASETS = ("LANDSAT/LC08/C02/T1_L2", "LANDSAT/LC09/C02/T1_L2")
ST_BAND = "ST_B10"
QA_BAND = "QA_PIXEL"
UNCERTAINTY_BAND = "ST_QA"
LST_BAND = "LST_K"

ST_SCALE = 0.00341802
ST_OFFSET = 149.0
ST_QA_SCALE = 0.01  # kelvin per count

# QA_PIXEL bit numbers (USGS Landsat Collection 2 Level 2 product guide): 1 dilated cloud, 2 cirrus, 3 cloud, 4 shadow.
QA_BITS = {"dilated_cloud": 1, "cirrus": 2, "cloud": 3, "cloud_shadow": 4}
QA_MASK = sum(1 << b for b in QA_BITS.values())

CSV_COLUMNS = ("block_id", "lst_kelvin", "valid_pixels")
BATCH = 100
"""Blocks per `reduceRegions` call."""


class HeatCheckError(RuntimeError):
    """The heat check cannot run; the message says what to do. The CLI prints it without a traceback."""


class EarthEngineError(HeatCheckError):
    """Earth Engine cannot be used: client not installed, not authorised, or the project is not enabled."""


class NoScenesError(HeatCheckError):
    """No usable Landsat scenes in the window or the year before."""


@dataclass(frozen=True)
class LstSettings:
    """Fixed method choices of the heat check. Pre-declared; changing one is a methodology change, not a tuning step."""

    datasets: tuple[str, ...] = DATASETS
    first_month: int = 3
    last_month: int = 5
    min_scenes: int = 5
    max_cloud_cover: float = 30.0
    """Scene-level `CLOUD_COVER` percent; a scene above it is not used at all."""
    max_st_uncertainty_k: float = 5.0
    scale_m: int = 30
    min_valid_pixels: int = 1
    crs: str = "EPSG:32643"


@dataclass(frozen=True)
class DateWindow:
    year: int
    start: date
    end: date
    """Inclusive."""

    @property
    def end_exclusive(self) -> date:
        return self.end + timedelta(days=1)

    @property
    def label(self) -> str:
        return f"{self.start.isoformat()}..{self.end.isoformat()}"


def season_window(year: int, settings: LstSettings) -> DateWindow:
    """March 1 to May 31 (inclusive) of `year` with the default months."""
    first = date(year, settings.first_month, 1)
    after = date(year + (settings.last_month == 12), settings.last_month % 12 + 1, 1)
    return DateWindow(year, first, after - timedelta(days=1))


@dataclass(frozen=True)
class BlockPolygon:
    block_id: str
    geometry: dict[str, Any]
    """GeoJSON geometry in WGS84."""


@dataclass(frozen=True)
class BlockReduction:
    block_id: str
    median_kelvin: float | None
    pixel_count: float
    """Coverage-weighted count of unmasked pixels, as Earth Engine's count reducer returns it."""


class LstBackend(Protocol):
    """What the step needs from Earth Engine; `EeBackend` is the real one, tests pass a fake."""

    def scene_count(self, dataset_id: str, window: DateWindow) -> int:
        """Scenes of one dataset over the area in the window that pass the scene-level cloud filter."""
        ...

    def reduce_blocks(self, blocks: Sequence[BlockPolygon], windows: Sequence[DateWindow]) -> list[BlockReduction]:
        """Median composite of the windows' scenes, reduced over each block with the median reducer."""
        ...

    def info(self) -> dict[str, str]:
        """Provenance of the connection: `project` and `earthengine_api_version`."""
        ...


# ---------- Earth Engine: connection ----------


def load_ee() -> Any:
    """Import `ee` here and nowhere else, so the pipeline and the api image never need it."""
    try:
        return importlib.import_module("ee")
    except ImportError as err:
        raise EarthEngineError(
            "earthengine-api is not installed. Run the heat check with the extra: "
            "uv run --package ecozone-pipeline --extra ee pipeline heat-check --area deccan"
        ) from err


def initialize(ee: Any, env: Mapping[str, str] | None = None) -> str:
    """Initialise Earth Engine and return the project used.

    The project is `$ECOZONE_EE_PROJECT` or `ecozone-ai-2026`. If `$ECOZONE_EE_ACCESS_TOKEN` is set (for example
    `gcloud auth print-access-token`), an OAuth credential with the Earth Engine and cloud-platform scopes is built
    from it; otherwise the stored credentials from `earthengine authenticate` or application default credentials are
    used. The token is never logged or written anywhere.
    """
    env = os.environ if env is None else env
    project = env.get(ENV_PROJECT) or DEFAULT_PROJECT
    token = env.get(ENV_TOKEN)
    try:
        if token:
            from google.oauth2.credentials import Credentials

            ee.Initialize(credentials=Credentials(token, scopes=list(EE_SCOPES)), project=project)
        else:
            ee.Initialize(project=project)
    except Exception as err:
        raise EarthEngineError(
            f"Earth Engine could not be initialised for project {project!r}: {err}. Needs either "
            "`earthengine authenticate`, or a gcloud token in ECOZONE_EE_ACCESS_TOKEN; the account needs "
            "roles/serviceusage.serviceUsageConsumer and roles/earthengine.viewer on the project "
            "(see evals/heat_check/README.md)."
        ) from err
    return project


def connect(cfg: AreaConfig, settings: LstSettings | None = None, env: Mapping[str, str] | None = None) -> EeBackend:
    """Import `ee`, initialise it and return the real backend."""
    ee = load_ee()
    project = initialize(ee, env)
    return EeBackend(ee, replace(settings or LstSettings(), crs=cfg.crs), cfg.bbox_wgs84, project)


# ---------- Earth Engine: the per-image maths ----------


def mask_and_scale(image: Any, settings: LstSettings) -> Any:
    """One scene to kelvin, masked. Uses only `Image` methods, so tests run it on a fake image.

    Masked: any `QA_PIXEL` bit of `QA_MASK`, fill (`ST_B10` = 0), and `ST_QA` outside 0 to the uncertainty limit.
    """
    qa = image.select(QA_BAND)
    st = image.select(ST_BAND)
    uncertainty = image.select(UNCERTAINTY_BAND)
    limit_counts = round(settings.max_st_uncertainty_k / ST_QA_SCALE)
    clear = qa.bitwiseAnd(QA_MASK).eq(0)
    not_fill = st.gt(0)
    reliable = uncertainty.gte(0).And(uncertainty.lte(limit_counts))
    kelvin = st.multiply(ST_SCALE).add(ST_OFFSET).rename(LST_BAND)
    return kelvin.updateMask(clear.And(not_fill).And(reliable))


class EeBackend:
    """The real backend over an `ee` module (passed in, so tests can use a fake)."""

    def __init__(
        self, ee: Any, settings: LstSettings, bbox_wgs84: tuple[float, float, float, float], project: str
    ) -> None:
        self._ee = ee
        self._settings = settings
        self._bbox = bbox_wgs84
        self._project = project

    def _scenes(self, dataset_id: str, window: DateWindow) -> Any:
        ee = self._ee
        return (
            ee.ImageCollection(dataset_id)
            .filterBounds(ee.Geometry.Rectangle(list(self._bbox)))
            .filterDate(window.start.isoformat(), window.end_exclusive.isoformat())
            .filter(ee.Filter.lt("CLOUD_COVER", self._settings.max_cloud_cover))
        )

    def scene_count(self, dataset_id: str, window: DateWindow) -> int:
        return int(self._scenes(dataset_id, window).size().getInfo())

    def composite(self, windows: Sequence[DateWindow]) -> Any:
        scenes: Any = None
        for window in windows:
            for dataset_id in self._settings.datasets:
                part = self._scenes(dataset_id, window)
                scenes = part if scenes is None else scenes.merge(part)
        return scenes.map(lambda image: mask_and_scale(image, self._settings)).median()

    def reduce_blocks(self, blocks: Sequence[BlockPolygon], windows: Sequence[DateWindow]) -> list[BlockReduction]:
        ee = self._ee
        image = self.composite(windows)
        reducer = ee.Reducer.median().combine(ee.Reducer.count(), sharedInputs=True)
        out: list[BlockReduction] = []
        for i in range(0, len(blocks), BATCH):
            features = [
                ee.Feature(ee.Geometry(b.geometry, "EPSG:4326", False), {"block_id": b.block_id})
                for b in blocks[i : i + BATCH]
            ]
            reduced = image.reduceRegions(
                collection=ee.FeatureCollection(features),
                reducer=reducer,
                scale=self._settings.scale_m,
                crs=self._settings.crs,
            ).getInfo()
            for feature in reduced["features"]:
                props = feature["properties"]
                median = props.get("median")
                out.append(
                    BlockReduction(
                        str(props["block_id"]),
                        None if median is None else float(median),
                        float(props.get("count") or 0.0),
                    )
                )
        return out

    def info(self) -> dict[str, str]:
        return {"project": self._project, "earthengine_api_version": str(getattr(self._ee, "__version__", "unknown"))}


# ---------- the step ----------


@dataclass(frozen=True)
class LstResult:
    table: pd.DataFrame
    """Columns `CSV_COLUMNS`, sorted by block id."""
    meta: dict[str, Any]


def block_polygons(blocks: gpd.GeoDataFrame, id_column: str = "id") -> list[BlockPolygon]:
    """Block polygons in WGS84 as GeoJSON, sorted by id (the bundle is in the metric CRS)."""
    if blocks.crs is None:
        raise ValueError("blocks have no CRS")
    wgs84 = blocks.to_crs(4326)
    polys = [
        BlockPolygon(str(i), json.loads(shapely.to_geojson(g)))
        for i, g in zip(wgs84[id_column], wgs84.geometry, strict=True)
    ]
    return sorted(polys, key=lambda p: p.block_id)


def reference_year(cfg: AreaConfig) -> int:
    return int(str(cfg["reference"]["date"])[:4])


def select_windows(
    backend: LstBackend, settings: LstSettings, year: int
) -> tuple[list[DateWindow], list[dict[str, Any]], int]:
    """The reference year, plus the year before if it has fewer than `min_scenes`. Returns windows, per-window scene
    counts for the record, and the total number of scenes."""
    windows: list[DateWindow] = []
    record: list[dict[str, Any]] = []
    total = 0
    for y in (year, year - 1):
        window = season_window(y, settings)
        counts = {ds: backend.scene_count(ds, window) for ds in settings.datasets}
        windows.append(window)
        record.append({"year": y, "start": window.start.isoformat(), "end": window.end.isoformat(), "scenes": counts})
        total += sum(counts.values())
        if total >= settings.min_scenes:
            break
    return windows, record, total


def fetch_block_lst(
    blocks: Sequence[BlockPolygon],
    backend: LstBackend,
    settings: LstSettings,
    year: int,
    fetched_on: date,
    bundle: Mapping[str, Any] | None = None,
) -> LstResult:
    """Median land surface temperature per block with provenance. Blocks with no valid pixel are dropped and listed."""
    windows, record, scenes = select_windows(backend, settings, year)
    if scenes == 0:
        raise NoScenesError(
            f"no Landsat 8/9 scenes under {settings.max_cloud_cover:g}% cloud cover in {windows[0].label} "
            f"or the year before; nothing to composite"
        )
    requested = {b.block_id for b in blocks}
    reductions = backend.reduce_blocks(blocks, windows)
    rows: list[tuple[str, float, int]] = []
    seen: set[str] = set()
    for r in reductions:
        if r.block_id not in requested or r.block_id in seen:
            continue
        seen.add(r.block_id)
        pixels = round(r.pixel_count)
        if r.median_kelvin is None or r.median_kelvin != r.median_kelvin or pixels < settings.min_valid_pixels:
            continue
        rows.append((r.block_id, round(r.median_kelvin, 4), pixels))
    table = pd.DataFrame(sorted(rows), columns=list(CSV_COLUMNS))
    kept = set(table["block_id"])
    pixels_sorted = sorted(int(p) for p in table["valid_pixels"])
    info = backend.info()
    meta: dict[str, Any] = {
        "kind": "block_lst",
        "area_id": (bundle or {}).get("area_id"),
        "bundle_version": (bundle or {}).get("bundle_version"),
        "bundle_settings_hash": (bundle or {}).get("settings_hash"),
        "datasets": list(settings.datasets),
        "band": ST_BAND,
        "scale_factor": ST_SCALE,
        "offset": ST_OFFSET,
        "output_units": "kelvin, internal and derived; never displayed",
        "qa_pixel_masked": {"bits": QA_BITS, "mask": QA_MASK},
        "st_qa_scale_k_per_count": ST_QA_SCALE,
        "st_qa_max_uncertainty_k": settings.max_st_uncertainty_k,
        "st_qa_note": "screening limit chosen by us before the run; USGS publishes no pass value",
        "scene_max_cloud_cover_pct": settings.max_cloud_cover,
        "windows": record,
        "years_used": [w.year for w in windows],
        "fallback_year_used": len(windows) > 1,
        "scenes_total": scenes,
        "min_scenes": settings.min_scenes,
        "min_scenes_met": scenes >= settings.min_scenes,
        "composite": "per-pixel median over unmasked values",
        "block_reducer": "median",
        "scale_m": settings.scale_m,
        "crs": settings.crs,
        "native_thermal_resolution_m": 100,
        "pixel_count": "coverage-weighted count of unmasked 30 m pixels, rounded to an integer",
        "fetch_date": fetched_on.isoformat(),
        "earth_engine_project": info.get("project"),
        "earthengine_api_version": info.get("earthengine_api_version"),
        "blocks_requested": len(requested),
        "blocks_with_lst": len(kept),
        "blocks_dropped": sorted(requested - kept),
        "valid_pixels_min": pixels_sorted[0] if pixels_sorted else None,
        "valid_pixels_median": pixels_sorted[len(pixels_sorted) // 2] if pixels_sorted else None,
        "valid_pixels_max": pixels_sorted[-1] if pixels_sorted else None,
    }
    return LstResult(table, meta)


def meta_path(csv_path: Path) -> Path:
    return csv_path.with_suffix(".meta.json")


def run(
    cfg: AreaConfig,
    paths: Paths,
    csv_path: Path,
    *,
    backend: LstBackend | None = None,
    bundle_dir: Path | None = None,
    today: date | None = None,
    settings: LstSettings | None = None,
) -> dict[str, Any]:
    """Read the bundle's blocks, fetch their land surface temperature and write the CSV and its provenance file."""
    bundle_dir = bundle_dir or paths.bundle(cfg.bundle_version)
    blocks_file = bundle_dir / "blocks.parquet"
    if not blocks_file.is_file():
        raise HeatCheckError(
            f"{blocks_file} not found. Build the bundle first (`uv run pipeline all --area {cfg.area_id}`) or pass "
            "--data-dir / ECOZONE_DATA_DIR / --out so the bundle can be found."
        )
    blocks = read_table(blocks_file)
    bundle_meta = read_json(bundle_dir / "meta.json") if (bundle_dir / "meta.json").is_file() else {}
    settings = replace(settings or LstSettings(), crs=cfg.crs)
    backend = backend or connect(cfg, settings)
    fetched_on = today or datetime.now(UTC).date()
    result = fetch_block_lst(block_polygons(blocks), backend, settings, reference_year(cfg), fetched_on, bundle_meta)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    result.table.to_csv(csv_path, index=False)
    write_json(result.meta, meta_path(csv_path))
    m = result.meta
    return {
        "blocks_requested": m["blocks_requested"],
        "blocks_with_lst": m["blocks_with_lst"],
        "blocks_dropped": len(m["blocks_dropped"]),
        "scenes": m["scenes_total"],
        "years_used": m["years_used"],
        "min_scenes_met": m["min_scenes_met"],
        "csv": str(csv_path),
    }
