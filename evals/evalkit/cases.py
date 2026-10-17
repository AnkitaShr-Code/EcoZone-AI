"""Typed view of evals/cases.yaml for one area."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

CASES_PATH = Path(__file__).resolve().parents[1] / "cases.yaml"
UNIT_COSTS_PATH = Path(__file__).resolve().parents[2] / "pipeline" / "config" / "unit_costs.yaml"


@dataclass(frozen=True)
class RepairCase:
    id: str
    budget_inr: float
    quick_win_share_pct: float


@dataclass(frozen=True)
class Design:
    floors: int
    footprint_pct: float
    green_pct: float
    orientation_deg: float


@dataclass(frozen=True)
class ProtectCase:
    id: str
    parcel_id: str
    proposal: Design
    keep_floor_area_pct: float
    min_floor_area_pct: float


@dataclass(frozen=True)
class GuardDesign:
    parcel_id: str
    design: Design


@dataclass(frozen=True)
class AreaCases:
    area_id: str
    bundle_version: str
    expected_split: dict[str, int]
    repair: tuple[RepairCase, ...]
    determinism_case: str
    speed_case: str
    direction_sites: dict[str, tuple[str, ...]]
    typical_portfolio: tuple[str, ...]
    protect: tuple[ProtectCase, ...]
    protect_search_case: str
    floors_ladder: tuple[int, ...]
    guard_designs: tuple[GuardDesign, ...]

    def repair_case(self, case_id: str) -> RepairCase:
        return next(c for c in self.repair if c.id == case_id)

    def protect_case(self, case_id: str) -> ProtectCase:
        return next(c for c in self.protect if c.id == case_id)


def _design(raw: dict[str, Any]) -> Design:
    return Design(
        floors=int(raw["floors"]),
        footprint_pct=float(raw["footprint_pct"]),
        green_pct=float(raw["green_pct"]),
        orientation_deg=float(raw["orientation_deg"]),
    )


def load_cases(area_id: str, path: Path = CASES_PATH) -> AreaCases:
    doc = cast("dict[str, Any]", yaml.safe_load(path.read_text()))
    areas = cast("dict[str, dict[str, Any]]", doc["areas"])
    if area_id not in areas:
        raise KeyError(f"evals/cases.yaml has no cases for area '{area_id}' (it has {sorted(areas)})")
    a = areas[area_id]
    return AreaCases(
        area_id=area_id,
        bundle_version=str(a["bundle_version"]),
        expected_split={str(k): int(v) for k, v in a["expected_split"].items()},
        repair=tuple(
            RepairCase(str(r["id"]), float(r["budget_inr"]), float(r["quick_win_share_pct"])) for r in a["repair"]
        ),
        determinism_case=str(a["determinism_case"]),
        speed_case=str(a["speed_case"]),
        direction_sites={str(k): tuple(str(s) for s in v) for k, v in a["direction_sites"].items()},
        typical_portfolio=tuple(str(s) for s in a["typical_portfolio"]),
        protect=tuple(
            ProtectCase(
                str(p["id"]),
                str(p["parcel_id"]),
                _design(p["proposal"]),
                float(p["keep_floor_area_pct"]),
                float(p["min_floor_area_pct"]),
            )
            for p in a["protect"]
        ),
        protect_search_case=str(a["protect_search_case"]),
        floors_ladder=tuple(int(f) for f in a["floors_ladder"]),
        guard_designs=tuple(GuardDesign(str(g["parcel_id"]), _design(g)) for g in a["guard_designs"]),
    )


def unit_cost_rows() -> dict[str, dict[str, Any]]:
    """Default unit costs (planner input) from pipeline/config/unit_costs.yaml."""
    return cast("dict[str, dict[str, Any]]", yaml.safe_load(UNIT_COSTS_PATH.read_text()))
