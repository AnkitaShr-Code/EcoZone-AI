"""The offline proposer (`ECOZONE_LLM=fake`): proposals by simple rules, so the whole app runs without Gemini.

It reads the same compact brief the model reads and returns site ids or design values. It never
computes a score: it orders sites by the engine's own single-site gains and costs, and the scorer
and the engine decide whether a proposal is valid and how good it is. Candidates carry
`source="gemini"` only because the contract has no other AI label; the run log says which proposer ran.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from .ports import DesignProposal, Proposal, ProposalRequest, RepairProposal
from .text import KIND_LABEL


@dataclass(frozen=True)
class _Site:
    id: str
    kind: str
    cost: float
    gain: float
    quick_win: bool

    @property
    def ratio(self) -> float:
        return self.gain / max(1.0, self.cost)


class RuleProposer:
    async def propose(self, request: ProposalRequest) -> list[Proposal]:
        if request.mode == "repair":
            return list(_repair(request))
        return list(_protect(request))


# ---------- Repair ----------


def _repair(request: ProposalRequest) -> Sequence[Proposal]:
    brief = request.brief
    budget = cast(float, brief["budget_inr"])
    target = cast(float, brief["quick_win_target_inr"])
    sites = [
        _Site(
            str(s["id"]), str(s["kind"]), cast(float, s["cost_inr"]), cast(float, s["acs_gain"]), bool(s["quick_win"])
        )
        for s in cast("list[dict[str, object]]", brief["sites"])
    ]
    by_ratio = sorted(sites, key=lambda s: (-s.ratio, s.id))
    by_id = {s.id: s for s in sites}

    def fill(order: Sequence[_Site], start: Sequence[_Site] = ()) -> list[_Site]:
        """Quick wins first until the target is met, then the rest in order, all within the budget."""
        picked = list(start)
        spent = sum(s.cost for s in picked)
        quick = sum(s.cost for s in picked if s.quick_win)

        def add(s: _Site) -> None:
            nonlocal spent, quick
            if s in picked or s.gain <= 0 or spent + s.cost > budget:
                return
            picked.append(s)
            spent += s.cost
            quick += s.cost if s.quick_win else 0.0

        for s in [*(x for x in order if x.quick_win), *(x for x in by_ratio if x.quick_win)]:
            if quick >= target:
                break
            add(s)
        for s in order:
            add(s)
        return picked

    def proposal(label: str, picked: Sequence[_Site]) -> RepairProposal:
        return RepairProposal(label, tuple((s.id, None) for s in picked))

    if request.round == 1:
        kinds = ["shade", "tree_row", "depave", "pocket_green", "cool_roof"]
        queues = [[s for s in by_ratio if s.kind == k] for k in kinds]
        mixed: list[_Site] = []
        while any(queues):
            for q in queues:
                if q:
                    mixed.append(q.pop(0))
        options = [
            ("Shade at waiting points first", fill([*(s for s in by_ratio if s.kind == "shade"), *by_ratio])),
            ("Biggest single gains first", fill(sorted(sites, key=lambda s: (-s.gain, s.id)))),
            ("A mix of intervention types", fill(mixed)),
            (
                "Green links and depaving first",
                fill([*(s for s in by_ratio if s.kind in ("pocket_green", "depave")), *by_ratio]),
            ),
        ]
        return [proposal(label, picked) for label, picked in options]

    best = cast("dict[str, object] | None", brief.get("best_so_far"))
    current = [by_id[i] for i in cast("list[str]", best["site_ids"]) if i in by_id] if best else []
    weakest = sorted(current, key=lambda s: (s.ratio, s.id))
    unused = [s for s in by_ratio if s not in current]
    out: list[Proposal] = []
    for i in range(request.count):
        drop = weakest[i % len(weakest)] if weakest else None
        add = next(
            (s for s in unused[i:] if drop is None or s.kind != drop.kind), unused[i] if i < len(unused) else None
        )
        keep = [s for s in current if s is not drop]
        if drop is not None and add is not None:
            label = f"Replace a {KIND_LABEL[drop.kind][0]} with a {KIND_LABEL[add.kind][0]}"
        else:
            label = "Use the remaining budget"
        out.append(proposal(label, fill([add, *unused] if add else unused, keep)))
    return out


# ---------- Protect ----------


def _protect(request: ProposalRequest) -> Sequence[Proposal]:
    brief = request.brief
    limits = cast("dict[str, float]", brief["limits"])
    wind = cast(float, brief["wind_axis_deg"])
    a = cast("dict[str, float]", brief["proposal"])

    def tweak(base: dict[str, float], label: str, **patch: float) -> DesignProposal:
        d = {**base, **patch}
        floors = max(1, min(limits["max_floors"], round(d["floors"])))
        footprint = max(10.0, min(limits["max_footprint_pct"], d["footprint_pct"]))
        green = max(limits["min_green_pct"], min(100 - footprint, d["green_pct"]))
        return DesignProposal(label, float(floors), footprint, green, d["orientation_deg"])

    if request.round == 1:
        options = [
            tweak(a, "Fewer floors", floors=a["floors"] * 0.7),
            tweak(
                a, "Smaller footprint, more green", footprint_pct=a["footprint_pct"] - 15, green_pct=a["green_pct"] + 15
            ),
            tweak(a, "Long side turned to the wind", orientation_deg=wind),
            tweak(
                a,
                "Lower and greener, turned to the wind",
                floors=a["floors"] * 0.5,
                green_pct=a["green_pct"] + 10,
                orientation_deg=wind,
            ),
        ]
        return options[: request.count]
    b = cast("dict[str, float] | None", brief.get("best_for_option_b")) or a
    c = cast("dict[str, float] | None", brief.get("best_for_option_c")) or b
    options = [
        tweak(b, "Option B: one floor lower", floors=b["floors"] - 1),
        tweak(
            b,
            "Option B: green on the wind side",
            footprint_pct=b["footprint_pct"] - 5,
            green_pct=b["green_pct"] + 5,
            orientation_deg=wind,
        ),
        tweak(c, "Option C: two floors lower", floors=c["floors"] - 2),
        tweak(c, "Option C: smaller footprint", footprint_pct=c["footprint_pct"] - 10, green_pct=c["green_pct"] + 10),
    ]
    return options[: request.count]
