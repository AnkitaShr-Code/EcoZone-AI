"""`ecozone-contract export`: write openapi.json from the models (contract/RULES.md).

The file holds `components.schemas` only; routes are described by the API's own OpenAPI document.
The app generates `app/src/api/generated.ts` from it with `npm run gen:api`.
"""

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, RootModel
from pydantic.json_schema import models_json_schema

from . import area, common, repair, runs

OPENAPI_PATH = Path(__file__).resolve().parents[2] / "openapi.json"


class Change(RootModel[repair.Change]):
    """One change to an area: an intervention on a site (Repair) or a building on a parcel (Protect)."""


class SearchRequest(RootModel[runs.SearchRequest]):
    """Body of POST /api/areas/{area}/runs."""


class SearchEvent(RootModel[runs.SearchEvent]):
    """One server-sent event of an agent run; `seq` is also the SSE id."""


MODELS: list[type[BaseModel]] = [
    common.ErrorBody,
    area.AreaSummary,
    area.UnitCosts,
    area.BlockLayer,
    area.SegmentLayer,
    area.BuildingLayer,
    area.WaitPointLayer,
    area.ParcelLayer,
    area.ShadowLayer,
    repair.Hotspot,
    repair.Site,
    Change,
    repair.RescoreRequest,
    repair.AreaResult,
    repair.RejectedOption,
    SearchRequest,
    runs.StartRunResponse,
    runs.ExplainRequest,
    runs.Explanation,
    runs.SearchResult,
    SearchEvent,
]


def build_openapi() -> dict[str, Any]:
    _, schema = models_json_schema(
        [(model, "serialization") for model in MODELS], ref_template="#/components/schemas/{model}"
    )
    return {
        "openapi": "3.1.0",
        "info": {"title": "EcoZone AI contract", "version": "0.1.0"},
        "paths": {},
        "components": {"schemas": schema.get("$defs", {})},
    }


def render() -> str:
    return json.dumps(build_openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    if sys.argv[1:] != ["export"]:
        sys.stderr.write("usage: ecozone-contract export\n")
        raise SystemExit(2)
    OPENAPI_PATH.write_text(render(), encoding="utf-8")
    sys.stdout.write(f"wrote {OPENAPI_PATH}\n")
