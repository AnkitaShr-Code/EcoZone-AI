"""Instant engine routes: rescore and the greedy baseline. Sync on purpose: the engine is CPU-bound."""

from fastapi import APIRouter

import ecozone_contract as c
from ecozone_contract.runs import RepairSearchRequest

from .. import to_contract
from ..deps import AreaDep, ServicesDep

router = APIRouter(prefix="/areas/{area_id}")


@router.post("/rescore")
def rescore(body: c.RescoreRequest, area: AreaDep, services: ServicesDep) -> c.AreaResult:
    """The one scoring path: Repair edits, Protect previews and build-out (ENGINEERING_RULES.md principle 3)."""
    result = services.engine.rescore(area, to_contract.changes(body.changes), to_contract.unit_costs(body.unit_costs))
    return to_contract.area_result(result)


@router.post("/greedy")
def greedy(body: RepairSearchRequest, area: AreaDep, services: ServicesDep) -> c.Candidate:
    portfolio = services.engine.greedy_baseline(
        area, body.budget_inr, to_contract.unit_costs(body.unit_costs), body.quick_win_share_pct
    )
    return to_contract.greedy_candidate(portfolio, body)
