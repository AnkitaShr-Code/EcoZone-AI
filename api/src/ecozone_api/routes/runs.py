"""Agent-run routes: start, stream (SSE), stop, explain (api/RULES.md)."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Header, Response
from fastapi.responses import StreamingResponse

import ecozone_contract as c

from ..deps import AreaDep, ServicesDep

router = APIRouter()


@router.post("/areas/{area_id}/runs", status_code=201)
async def start_run(body: c.SearchRequest, area: AreaDep, services: ServicesDep) -> c.StartRunResponse:
    run = services.runs.start(area, body)
    return c.StartRunResponse(run_id=run.id)


@router.get(
    "/runs/{run_id}/events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "SearchEvent stream; id = seq"}},
)
async def run_events(
    run_id: str,
    services: ServicesDep,
    last_event_id: Annotated[int | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    services.runs.get(run_id)  # 404 before the stream starts
    events = services.runs.events(run_id, after_seq=last_event_id or 0)

    async def stream() -> AsyncIterator[str]:
        async for event in events:
            if event is None:
                yield ": heartbeat\n\n"
            else:
                yield f"id: {event.seq}\nevent: {event.type}\ndata: {event.model_dump_json()}\n\n"

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(stream(), media_type="text/event-stream", headers=headers)


@router.delete("/runs/{run_id}", status_code=204)
async def stop_run(run_id: str, services: ServicesDep) -> Response:
    await services.runs.stop(run_id)
    return Response(status_code=204)


@router.post("/areas/{area_id}/explain")
async def explain(body: c.ExplainRequest, area: AreaDep, services: ServicesDep) -> c.Explanation:
    return await services.runs.runner.explain(area, body.changes, body.unit_costs)
