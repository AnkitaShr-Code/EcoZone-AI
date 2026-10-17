"""Protect mode of the search: building designs for one parcel, options A, B and C.

docs/PLANNING.md "Design search loop (Protect)". The model proposes designs; every design is scored
with a `building` change through `rescore`, and the options are chosen from scored candidates only.
"""

import asyncio
from collections.abc import Sequence
from typing import Literal

import ecozone_contract as c
import ecozone_engine as e
from ecozone_contract.runs import ProtectSearchRequest

from . import to_contract as tc
from .catalog import ParcelInfo
from .config import AgentSettings
from .explain import write_explanation
from .facts import protect_facts
from .ports import DesignProposal, Emit, EnginePort, Proposal, Writer
from .search import NEG_INF, Scored
from .text import INDEX_WORDS, fmt_pct, fmt_score

ORIENTATION_STEP = 15.0
"""Orientation moves in 15 degree steps (docs/PLANNING.md, design search levers)."""
NO_GAIN = 0.5
"""A worst-change improvement smaller than this counts as no improvement in the trade-off text."""
MIN_FOOTPRINT_PCT = 10.0
DROP_REASONS_SHOWN = 6
_EPS = 1e-9


def floor_area(floors: float, footprint_pct: float) -> float:
    """Floor area proxy: footprint percentage times floors (docs/PLANNING.md, Protect)."""
    return floors * footprint_pct


def wind_axis_deg(wind_from_deg: float) -> float:
    """The wind's axis folded into 0-180 and snapped to the orientation step."""
    return (round((wind_from_deg % 180) / ORIENTATION_STEP) * ORIENTATION_STEP) % 180


class ProtectMode:
    name = "protect"

    def __init__(
        self,
        *,
        engine: EnginePort,
        area: e.AreaModel,
        request: ProtectSearchRequest,
        unit_costs: c.UnitCosts,
        parcel: ParcelInfo | None,
        settings: AgentSettings,
        wind_from_deg: float,
        reference_date: str | None = None,
    ) -> None:
        self.engine = engine
        self.area = area
        self.request = request
        self.costs = tc.engine_unit_costs(unit_costs)
        self.unit_costs = unit_costs
        self.parcel = parcel
        self.settings = settings
        self.wind_from_deg = wind_from_deg
        self.reference_date = reference_date
        self.proposal = request.proposal
        self._base_area = floor_area(self.proposal.floors, self.proposal.footprint_pct)
        self._seen: set[tuple[float, float, float, float]] = set()
        self._a: Scored | None = None

    # ---------- baseline ----------

    def _pct_of_a(self, floors: float, footprint_pct: float) -> float:
        return round(100 * floor_area(floors, footprint_pct) / self._base_area, 1) if self._base_area else 0.0

    async def baseline(self) -> Scored:
        design = self.proposal
        change = tc.building_change(self.request.parcel_id, design)
        result = await asyncio.to_thread(self.engine.rescore, self.area, [change], self.costs)
        self._seen.add(_design_key(design.floors, design.footprint_pct, design.green_pct, design.orientation_deg))
        candidate = c.Candidate(
            id="proposal",
            round=0,
            source="proposal",
            label="As proposed",
            changes=[tc.contract_change(change)],
            score=tc.score(result.risk.change) if result.risk else 0.0,
            cost_inr=0.0,
            floor_area_pct=100.0,
            risk=tc.risk(result.risk) if result.risk else None,
            valid=True,
        )
        self._a = Scored(candidate, result.risk.change if result.risk else 0.0, (change,), result, design)
        return self._a

    # ---------- scoring ----------

    def _range_problem(self, p: DesignProposal) -> str | None:
        """Why a design is outside the ranges: not above the proposal's height or footprint, not less green."""
        a = self.proposal
        floors = round(p.floors)
        if floors < 1:
            return "Fewer than one floor"
        if floors > a.floors:
            return "Taller than the proposal"
        if p.footprint_pct <= 0 or p.footprint_pct > a.footprint_pct + _EPS:
            return "Footprint is zero or larger than the proposal"
        if p.green_pct < a.green_pct - _EPS or p.green_pct > 100:
            return "Less green than the proposal"
        if p.footprint_pct + p.green_pct > 100 + _EPS:
            return "Footprint and green add up to more than 100%"
        if (
            not 0 <= p.orientation_deg < 180
            or abs(p.orientation_deg / ORIENTATION_STEP - round(p.orientation_deg / ORIENTATION_STEP)) > _EPS
        ):
            return "Orientation must be a 15° step from 0 up to 180"
        return None

    def _dropped(self, cid: str, round_no: int, p: DesignProposal, reason: str) -> Scored:
        assert self._a is not None
        floors = round(p.floors)
        design = _try_design(floors, p.footprint_pct, p.green_pct, p.orientation_deg)
        change = tc.building_change(self.request.parcel_id, design) if design else None
        candidate = c.Candidate(
            id=cid,
            round=round_no,
            source="gemini",
            label=p.label,
            changes=[tc.contract_change(change)] if change else [],
            score=self._a.candidate.score,
            cost_inr=0.0,
            floor_area_pct=self._pct_of_a(floors, p.footprint_pct),
            valid=False,
            invalid_reason=reason,
        )
        return Scored(candidate, NEG_INF, (change,) if change else (), None, design)

    async def score(self, proposal: Proposal, round_no: int, ordinal: int) -> Scored | None:
        assert isinstance(proposal, DesignProposal)
        cid = f"d{ordinal}"
        if problem := self._range_problem(proposal):
            return self._dropped(cid, round_no, proposal, problem)
        floors = round(proposal.floors)
        key = _design_key(floors, proposal.footprint_pct, proposal.green_pct, proposal.orientation_deg)
        if key in self._seen:
            return None
        self._seen.add(key)
        pct = self._pct_of_a(floors, proposal.footprint_pct)
        min_pct = self.request.min_floor_area_pct
        if pct < min_pct:
            return self._dropped(cid, round_no, proposal, f"Keeps less than {fmt_pct(min_pct)} of the floor area")
        design = c.BuildingDesign(
            floors=floors,
            footprint_pct=proposal.footprint_pct,
            green_pct=proposal.green_pct,
            orientation_deg=proposal.orientation_deg,
        )
        change = tc.building_change(self.request.parcel_id, design)
        try:
            result = await asyncio.to_thread(self.engine.rescore, self.area, [change], self.costs)
        except e.EngineInputError as exc:
            return self._dropped(cid, round_no, proposal, str(exc))
        if result.risk is None:
            return self._dropped(cid, round_no, proposal, "The engine returned no risk label for this design")
        candidate = c.Candidate(
            id=cid,
            round=round_no,
            source="gemini",
            label=proposal.label,
            changes=[tc.contract_change(change)],
            score=tc.score(result.risk.change),
            cost_inr=0.0,
            floor_area_pct=pct,
            risk=tc.risk(result.risk),
            valid=True,
        )
        return Scored(candidate, result.risk.change, (change,), result, design)

    # ---------- option selection ----------

    @staticmethod
    def pick(scored: Sequence[Scored], min_floor_area_pct: float) -> Scored | None:
        """Lowest worst change among valid designs keeping at least this share of A's floor area.

        Ties go to the design keeping more floor area, then to the earlier candidate.
        """
        pool = [
            (i, s) for i, s in enumerate(scored) if s.valid and (s.candidate.floor_area_pct or 0) >= min_floor_area_pct
        ]
        if not pool:
            return None
        return min(pool, key=lambda item: (item[1].value, -(item[1].candidate.floor_area_pct or 0), item[0]))[1]

    def objectives(self, scored: Sequence[Scored]) -> tuple[float, ...]:
        """Negated worst change of the current B and C picks, so higher is better like Repair."""
        picks = (
            self.pick(scored, self.request.keep_floor_area_pct),
            self.pick(scored, self.request.min_floor_area_pct),
        )
        return tuple(-p.value if p else NEG_INF for p in picks)

    # ---------- the proposer's view ----------

    def brief(self, scored: Sequence[Scored], round_no: int) -> dict[str, object]:
        a = self.proposal
        assert self._a is not None
        r = self.request

        def entry(s: Scored | None) -> dict[str, object] | None:
            if s is None or s.design is None:
                return None
            d = s.design
            return {
                "label": s.candidate.label,
                "floors": d.floors,
                "footprint_pct": d.footprint_pct,
                "green_pct": d.green_pct,
                "orientation_deg": d.orientation_deg,
                "worst_change": s.candidate.score,
                "floor_area_pct": s.candidate.floor_area_pct,
            }

        previous = [s for s in scored if s.candidate.round == round_no - 1 and round_no > 1 and not s.valid]
        return {
            "parcel": {"id": r.parcel_id, "name": self.parcel.name if self.parcel else r.parcel_id},
            "proposal": entry(self._a),
            "keep_floor_area_pct": r.keep_floor_area_pct,
            "min_floor_area_pct": r.min_floor_area_pct,
            "limits": {
                "max_floors": a.floors,
                "max_footprint_pct": a.footprint_pct,
                "min_green_pct": a.green_pct,
                "orientation_step_deg": ORIENTATION_STEP,
            },
            "wind_axis_deg": wind_axis_deg(self.wind_from_deg),
            "best_for_option_b": entry(self.pick(scored, r.keep_floor_area_pct)),
            "best_for_option_c": entry(self.pick(scored, r.min_floor_area_pct)),
            "dropped_last_round": [
                {"label": s.candidate.label, "reason": s.candidate.invalid_reason}
                for s in previous[:DROP_REASONS_SHOWN]
            ],
        }

    # ---------- the result ----------

    @staticmethod
    def _worst(s: Scored) -> str:
        risk = s.candidate.risk
        if risk is None:
            return ""
        words, direction = INDEX_WORDS[risk.index]
        return f" Worst change: {words} {direction} by {fmt_score(risk.change)} ({risk.label.lower()} risk)."

    def _options(self, a: Scored, b: Scored, c_pick: Scored) -> list[c.DesignOption]:
        def option(key: Literal["A", "B", "C"], title: str, s: Scored, trade_off: str) -> c.DesignOption:
            assert s.design is not None
            return c.DesignOption(key=key, title=title, candidate=s.candidate, design=s.design, trade_off=trade_off)

        def keeps(s: Scored) -> str:
            return f"Keeps {fmt_pct(s.candidate.floor_area_pct or 0)} of the floor area."

        def no_gain(s: Scored) -> str:
            return " No design at this share lowers the worst change." if s.value >= a.value - NO_GAIN else ""

        return [
            option("A", "Developer maximised", a, "All the proposed floor area." + self._worst(a)),
            option("B", "Balanced", b, keeps(b) + self._worst(b) + no_gain(b)),
            option("C", "Climate optimised", c_pick, keeps(c_pick) + self._worst(c_pick) + no_gain(c_pick)),
        ]

    async def finish(
        self, scored: Sequence[Scored], rounds: int, *, writer: Writer | None, emit: Emit
    ) -> c.SearchResult:
        assert self._a is not None
        a = self._a
        b = self.pick(scored, self.request.keep_floor_area_pct) or a
        c_pick = self.pick(scored, self.request.min_floor_area_pct) or b
        options = self._options(a, b, c_pick)
        assert a.result is not None
        facts = protect_facts(
            proposal=self.proposal,
            result=a.result,
            parcel=self.parcel,
            parcel_id=self.request.parcel_id,
            options=options,
            keep_floor_area_pct=self.request.keep_floor_area_pct,
            min_floor_area_pct=self.request.min_floor_area_pct,
            rounds=rounds,
            reference_date=self.reference_date,
        )
        explanation = await write_explanation(writer, facts, self.settings, emit)
        return c.SearchResult(
            best=b.candidate,
            gemini_beat_greedy=None,
            options=options,
            rejected=[],
            rounds=rounds,
            explanation=explanation,
        )


def _design_key(floors: float, footprint: float, green: float, orientation: float) -> tuple[float, float, float, float]:
    return (float(floors), round(footprint, 6), round(green, 6), round(orientation, 6))


def _try_design(floors: int, footprint: float, green: float, orientation: float) -> c.BuildingDesign | None:
    try:
        return c.BuildingDesign(floors=floors, footprint_pct=footprint, green_pct=green, orientation_deg=orientation)
    except ValueError:
        return None
