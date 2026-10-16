"""Area config and the on-disk layout of the work directory and bundle (pipeline/RULES.md)."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
DEFAULT_DATA_DIR = "data"


@dataclass(frozen=True)
class AreaConfig:
    """Parsed `config/<area>.yaml`. Code reads settings from `raw`; nothing branches on the area name."""

    raw: dict[str, Any]
    base_dir: Path = CONFIG_DIR

    @property
    def area_id(self) -> str:
        return str(self.raw["area"]["id"])

    @property
    def crs(self) -> str:
        return str(self.raw["area"]["crs"])

    @property
    def bbox_wgs84(self) -> tuple[float, float, float, float]:
        w, s, e, n = (float(v) for v in self.raw["area"]["bbox_wgs84"])
        return (w, s, e, n)

    @property
    def bundle_version(self) -> int:
        return int(self.raw["area"]["bundle_version"])

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    @property
    def settings_hash(self) -> str:
        canonical = json.dumps(self.raw, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()


def load_config(area: str, config_path: Path | None = None) -> AreaConfig:
    path = config_path or CONFIG_DIR / f"{area}.yaml"
    raw = cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))
    return AreaConfig(raw, path.parent)


@dataclass(frozen=True)
class Paths:
    """Where one area's intermediate files and bundle live under the data directory."""

    data_dir: Path
    area_id: str

    @classmethod
    def for_area(cls, area_id: str, data_dir: Path | None = None) -> Paths:
        return cls(data_dir or Path(os.environ.get("ECOZONE_DATA_DIR", DEFAULT_DATA_DIR)), area_id)

    @property
    def work(self) -> Path:
        return self.data_dir / "work" / self.area_id

    @property
    def raw(self) -> Path:
        return self.work / "raw"

    def bundle(self, version: int) -> Path:
        return self.data_dir / "areas" / self.area_id / f"v{version}"

    def table(self, name: str) -> Path:
        return self.work / f"{name}.parquet"

    def json(self, name: str) -> Path:
        return self.work / f"{name}.json"
