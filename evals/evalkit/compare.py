"""Gemini-vs-greedy comparison helpers: win, tie or loss on engine ACS values (no pass mark)."""

import json
from typing import Any

import ecozone_engine as e

from .adapter import change_key
from .bench import Bench, SearchRun
from .cases import RepairCase

TIE_BAND = 0.05
"""ACS points. Scores are shown to one decimal, so a difference under half of that is a tie."""


def classify(ai: float, greedy: float) -> str:
    if ai - greedy > TIE_BAND:
        return "win"
    if greedy - ai > TIE_BAND:
        return "loss"
    return "tie"


def best_ai_acs(bench: Bench, run: SearchRun) -> tuple[float | None, float | None, int, int]:
    """(best valid AI plan's raw ACS, its cost, valid AI candidates, all AI candidates), from engine values."""
    best: tuple[float, float] | None = None
    valid = total = 0
    for raw in run.events:
        ev: dict[str, Any] = json.loads(raw)
        if ev["type"] != "candidate" or ev["candidate"]["source"] != "gemini":
            continue
        total += 1
        cand = ev["candidate"]
        if not cand["valid"]:
            continue
        valid += 1
        changes = [e.Change(kind=ch["kind"], site_id=ch["siteId"], quantity=ch["quantity"]) for ch in cand["changes"]]
        result = run.engine.rescored.get(change_key(changes)) or bench.rescore(changes)
        if best is None or result.after.acs > best[0]:
            best = (result.after.acs, result.cost_inr)
    return (best[0], best[1], valid, total) if best else (None, None, valid, total)


def baseline_candidate(run: SearchRun) -> dict[str, Any]:
    """The greedy plan as the loop scored it (the `baseline` event), with its validity."""
    for raw in run.events:
        ev: dict[str, Any] = json.loads(raw)
        if ev["type"] == "baseline":
            return ev["candidate"]
    raise AssertionError("the search emitted no baseline event")


def compare(bench: Bench, rc: RepairCase, run: SearchRun) -> dict[str, Any]:
    greedy = bench.greedy_for(rc).portfolio.result
    base = baseline_candidate(run)
    ai_acs, ai_cost, valid, total = best_ai_acs(bench, run)
    row: dict[str, Any] = {
        "greedy_acs": round(greedy.after.acs, 3),
        "greedy_cost_inr": round(greedy.cost_inr),
        "baseline_acs": round(greedy.before.acs, 3),
        "ai_acs": None if ai_acs is None else round(ai_acs, 3),
        "ai_cost_inr": None if ai_cost is None else round(ai_cost),
        # By ACS alone. `reported_gemini_beat_greedy` is the loop's own verdict, which also counts a greedy plan that
        # breaks a rule (quick-win share, budget, ventilation) as beaten by any valid AI plan.
        "outcome": "loss" if ai_acs is None else classify(ai_acs, greedy.after.acs),
        "delta": None if ai_acs is None else round(ai_acs - greedy.after.acs, 3),
        "greedy_valid": base["valid"],
        "greedy_invalid_reason": base.get("invalidReason"),
        "ai_valid_candidates": valid,
        "ai_candidates": total,
        "rounds": run.result.rounds,
        "reported_gemini_beat_greedy": run.result.gemini_beat_greedy,
        "search_seconds": round(run.seconds, 1),
    }
    return row
