"""Repair mode of the search: portfolios of interventions scored against a greedy baseline.

docs/PLANNING.md "Portfolio search loop (Repair)". The model proposes site ids and quantities; every
score, cost and check below comes from the engine (`rescore`, `greedy_baseline`, `single_site`).
"""

import asyncio
from collections.abc import Sequence
from typing import Literal

import ecozone_contract as c
import ecozone_engine as e
from ecozone_contract.runs import RepairSearchRequest

from . import to_contract as tc
from .catalog import SiteInfo
from .config import AgentSettings
from .explain import write_explanation
from .facts import repair_facts
from .ports import Emit, EnginePort, Proposal, RepairProposal, Writer
from .search import NEG_INF, Scored

GREEDY_LABEL = "Quick wins, then best gain per rupee"
DROP_REASONS_SHOWN = 6


class RepairMode:
    name = "repair"

    def __init__(
        self,
        *,
        engine: EnginePort,
        area: e.AreaModel,
        request: RepairSearchRequest,
        sites: dict[str, SiteInfo],
        settings: AgentSettings,
        reference_date: str | None = None,
    ) -> None:
        self.engine = engine
        self.area = area
        self.request = request
        self.sites = sites
        self.settings = settings
        self.reference_date = reference_date
        self.costs = tc.engine_unit_costs(request.unit_costs)
        self.quick_win_target_inr = request.budget_inr * request.quick_win_share_pct / 100
        self._seen: set[tuple[tuple[str, float], ...]] = set()
        self._greedy: Scored | None = None
        self._baseline_acs = 0.0

    # ---------- baseline ----------

    async def baseline(self) -> Scored:
        r = self.request
        portfolio = await asyncio.to_thread(
            self.engine.greedy_baseline, self.area, r.budget_inr, self.costs, r.quick_win_share_pct
        )
        self._baseline_acs = portfolio.result.before.acs
        self._seen.add(_key(portfolio.changes))
        self._greedy = self._scored("greedy", 0, "greedy", GREEDY_LABEL, portfolio.changes, portfolio.result)
        return self._greedy

    # ---------- scoring ----------

    def _invalid_reason(self, result: e.AreaResultData) -> str | None:
        """Why a scored portfolio cannot be shown as valid (docs/PLANNING.md step 5)."""
        if tc.inr(result.cost_inr) > self.request.budget_inr:
            return "Over budget"
        if tc.inr(result.quick_win_cost_inr) < self.quick_win_target_inr - 1e-6:
            return "Below the quick-win share"
        if not result.ventilation_ok:
            return "Fails the ventilation check"
        return None

    def _scored(
        self,
        cid: str,
        round_no: int,
        source: Literal["gemini", "greedy"],
        label: str,
        changes: Sequence[e.Change],
        result: e.AreaResultData,
    ) -> Scored:
        reason = self._invalid_reason(result)
        candidate = c.Candidate(
            id=cid,
            round=round_no,
            source=source,
            label=label,
            changes=[tc.contract_change(ch) for ch in changes],
            score=tc.score(result.after.acs),
            cost_inr=tc.inr(result.cost_inr),
            valid=reason is None,
            invalid_reason=reason,
        )
        return Scored(candidate, result.after.acs, tuple(changes), result)

    def _dropped(self, cid: str, round_no: int, label: str, changes: Sequence[e.Change], reason: str) -> Scored:
        """A candidate the engine never scored (unknown site, refused change): kept with its reason."""
        candidate = c.Candidate(
            id=cid,
            round=round_no,
            source="gemini",
            label=label,
            changes=[tc.contract_change(ch) for ch in changes],
            score=tc.score(self._baseline_acs),
            cost_inr=0.0,
            valid=False,
            invalid_reason=reason,
        )
        return Scored(candidate, NEG_INF, tuple(changes))

    def _resolve(self, proposal: RepairProposal) -> tuple[list[e.Change], str | None]:
        """Turn a proposal into engine changes, or say why it cannot be scored."""
        changes: list[e.Change] = []
        seen: set[str] = set()
        for site_id, quantity in proposal.changes:
            site = self.sites.get(site_id)
            if site is None:
                return changes, f"Site {site_id} is not in this area"
            if site_id in seen:
                return changes, f"Site {site_id} appears twice"
            seen.add(site_id)
            if not site.ventilation_ok:
                return changes, site.ventilation_reason or f"Site {site_id} is rejected by the ventilation check"
            amount = site.quantity if quantity is None else quantity
            if amount <= 0:
                return changes, f"Site {site_id} needs a quantity above zero"
            changes.append(tc.intervention_change(site.kind, site_id, amount))
        if not changes:
            return changes, "The portfolio has no sites"
        return sorted(changes, key=lambda ch: ch.site_id), None

    async def score(self, proposal: Proposal, round_no: int, ordinal: int) -> Scored | None:
        assert isinstance(proposal, RepairProposal)
        cid = f"c{ordinal}"
        changes, problem = self._resolve(proposal)
        if problem is not None:
            return self._dropped(cid, round_no, proposal.label, changes, problem)
        key = _key(changes)
        if key in self._seen:
            return None
        self._seen.add(key)
        try:
            result = await asyncio.to_thread(self.engine.rescore, self.area, changes, self.costs)
        except e.EngineInputError as exc:
            return self._dropped(cid, round_no, proposal.label, changes, str(exc))
        return self._scored(cid, round_no, "gemini", proposal.label, changes, result)

    # ---------- the proposer's view ----------

    def objectives(self, scored: Sequence[Scored]) -> tuple[float, ...]:
        return (max((s.value for s in scored if s.valid), default=NEG_INF),)

    def brief(self, scored: Sequence[Scored], round_no: int) -> dict[str, object]:
        r = self.request
        usable = [s for s in self.sites.values() if s.ventilation_ok and s.acs_gain > 0 and s.cost_inr <= r.budget_inr]
        usable.sort(key=lambda s: (-s.acs_gain / max(1.0, s.cost_inr), s.id))
        shown = self._sites_shown(usable)
        best = max((s for s in scored if s.valid), key=lambda s: s.value, default=None)
        previous = [s for s in scored if s.candidate.round == round_no - 1 and not s.valid and s.candidate.round > 0]
        return {
            "budget_inr": tc.inr(r.budget_inr),
            "quick_win_target_inr": tc.inr(self.quick_win_target_inr),
            "quick_win_time_to_benefit": ["weeks", "season"],
            "unit_costs_inr": {kind: tc.inr(getattr(r.unit_costs, kind).inr) for kind in tc.KINDS},
            "sites": [
                {
                    "id": s.id,
                    "kind": s.kind,
                    "name": s.name,
                    "quantity": s.quantity,
                    "cost_inr": tc.inr(s.cost_inr),
                    "acs_gain": round(s.acs_gain, 2),
                    "time_to_benefit": s.time_to_benefit,
                    "quick_win": s.quick_win,
                }
                for s in shown
            ],
            "greedy": _plan(self._greedy),
            "best_so_far": _plan(best),
            "dropped_last_round": [
                {"label": s.candidate.label, "reason": s.candidate.invalid_reason}
                for s in previous[:DROP_REASONS_SHOWN]
            ],
        }

    def _sites_shown(self, usable: Sequence[SiteInfo]) -> list[SiteInfo]:
        """Cap the list the model sees without starving it of quick wins. Sorted by gain per rupee, the
        cap alone is filled with tree rows, which are not quick wins, so the model could not meet the share."""
        cap = self.settings.max_sites_in_prompt
        quick = [s for s in usable if s.quick_win][: cap // 2]
        others = [s for s in usable if not s.quick_win][: cap - len(quick)]
        return sorted([*quick, *others], key=lambda s: (-s.acs_gain / max(1.0, s.cost_inr), s.id))

    # ---------- the result ----------

    def rejected(self) -> tuple[list[c.RejectedOption], int]:
        """Sites the ventilation or site rule refuses, deepest and narrowest street first (docs/PLANNING.md step 6)."""
        refused = sorted(
            (s for s in self.sites.values() if not s.ventilation_ok), key=lambda s: (-(s.h_w or 0.0), -s.acs_gain, s.id)
        )
        options = [
            c.RejectedOption(
                site_id=s.id,
                driver="CANOPY_OBSTRUCTION",
                reason=s.ventilation_reason or "Rejected by the ventilation check.",
            )
            for s in refused[: self.settings.rejected_shown]
        ]
        return options, len(refused)

    async def finish(
        self, scored: Sequence[Scored], rounds: int, *, writer: Writer | None, emit: Emit
    ) -> c.SearchResult:
        """Pick the best valid candidate, say whether Gemini beat greedy, and write the explanation."""
        assert self._greedy is not None
        greedy = self._greedy
        ai = [s for s in scored if s.candidate.source == "gemini" and s.valid]
        best_ai = max(ai, key=lambda s: (s.value, -s.candidate.cost_inr), default=None)
        # Strictly better, or greedy is itself unusable: otherwise the simpler baseline plan is the answer.
        beat = best_ai is not None and (not greedy.valid or best_ai.value > greedy.value)
        chosen = best_ai if beat and best_ai is not None else greedy
        assert chosen.result is not None
        rejected, rejected_total = self.rejected()
        facts = repair_facts(
            result=chosen.result,
            changes=chosen.changes,
            sites=self.sites,
            budget_inr=self.request.budget_inr,
            quick_win_share_pct=self.request.quick_win_share_pct,
            unit_costs=self.request.unit_costs,
            greedy=(greedy.value, greedy.candidate.cost_inr),
            plan_source=chosen.candidate.source,
            gemini_beat_greedy=beat,
            rejected=rejected,
            rejected_total=rejected_total,
            rounds=rounds,
            reference_date=self.reference_date,
        )
        explanation = await write_explanation(writer, facts, self.settings, emit)
        return c.SearchResult(
            best=chosen.candidate,
            gemini_beat_greedy=beat,
            options=None,
            rejected=rejected,
            rounds=rounds,
            explanation=explanation,
        )


def _key(changes: Sequence[e.Change]) -> tuple[tuple[str, float], ...]:
    return tuple(sorted((ch.site_id, ch.quantity) for ch in changes))


def _plan(s: Scored | None) -> dict[str, object] | None:
    if s is None:
        return None
    return {
        "label": s.candidate.label,
        "site_ids": [ch.site_id for ch in s.changes],
        "score": s.candidate.score,
        "cost_inr": s.candidate.cost_inr,
        "quick_win_cost_inr": tc.inr(s.result.quick_win_cost_inr) if s.result else None,
    }
