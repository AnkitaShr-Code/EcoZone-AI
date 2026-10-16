"""Read routes: area summary, map layers, shadows, hotspots, candidate sites (api/RULES.md)."""

from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response
from pydantic import TypeAdapter, ValidationError

import ecozone_contract as c
from ecozone_contract.common import InterventionType, LayerName, ShadeTime

from .. import to_contract
from ..deps import AreaDep, ServicesDep, sites
from ..errors import ApiError

router = APIRouter(prefix="/areas/{area_id}")

_CHANGES = TypeAdapter(list[c.Change])
_LAYER_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {"model": c.BlockLayer | c.SegmentLayer | c.BuildingLayer | c.WaitPointLayer | c.ParcelLayer},
    304: {"description": "Not modified since the ETag (the bundle version)"},
}


@router.get("")
def area_summary(area: AreaDep, services: ServicesDep) -> c.AreaSummary:
    return services.cached(
        area.area_id,
        "summary",
        lambda: to_contract.summary(services.engine.summary(area), services.unit_cost_defaults),
    )


def _json_cached(request: Request, etag: str, body: bytes) -> Response:
    """Layers depend only on the bundle, so the bundle version is a strong ETag."""
    headers = {"ETag": etag, "Cache-Control": "public, max-age=300"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)


@router.get("/layers/{name}", response_model=None, responses=_LAYER_RESPONSES)
def area_layer(name: LayerName, area: AreaDep, services: ServicesDep, request: Request) -> Response:
    def compute() -> bytes:
        features = services.engine.layer(area, to_contract.ENGINE_LAYER[name])
        return to_contract.layer(name, features).model_dump_json().encode()

    body = services.cached(area.area_id, f"layer:{name}", compute)
    return _json_cached(request, f'"{area.bundle_version}"', body)


@router.get("/shadows", response_model=None, responses={200: {"model": c.ShadowLayer}})
def area_shadows(
    area: AreaDep,
    services: ServicesDep,
    request: Request,
    t: ShadeTime,
    changes: Annotated[str | None, Query(description="JSON array of Change; omit for today's shadows.")] = None,
) -> Response:
    if not changes:

        def compute() -> bytes:
            return to_contract.shadow_layer(services.engine.shadows(area, t)).model_dump_json().encode()

        body = services.cached(area.area_id, f"shadows:{t}", compute)
        return _json_cached(request, f'"{area.bundle_version}-{t}"', body)
    try:
        parsed = _CHANGES.validate_json(changes)
    except ValidationError as exc:
        raise ApiError(
            "INVALID_REQUEST", f"changes is not a valid list of changes: {exc.errors()[0]['msg']}.", 422
        ) from exc
    polygons = services.engine.shadows(area, t, to_contract.changes(parsed))
    return Response(content=to_contract.shadow_layer(polygons).model_dump_json(), media_type="application/json")


@router.get("/hotspots")
def area_hotspots(
    area: AreaDep, services: ServicesDep, top: Annotated[int, Query(ge=1, le=100)] = 10
) -> list[c.Hotspot]:
    return [to_contract.hotspot(h) for h in services.engine.hotspots(area, top)]


@router.get("/sites")
def area_sites(
    area: AreaDep,
    services: ServicesDep,
    types: Annotated[str | None, Query(description="Comma-separated intervention types; omit for all.")] = None,
) -> list[c.Site]:
    all_sites = sites(services, area)
    if not types:
        return all_sites
    wanted = set(TypeAdapter(list[InterventionType]).validate_python(types.split(",")))
    return [s for s in all_sites if s.type in wanted]
