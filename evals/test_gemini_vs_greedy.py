"""Gemini vs greedy (docs/PLANNING.md, Trust and evaluation): win, tie or loss per case with both ACS values.

There is no pass mark. This module runs the search loop with the offline rule proposer (`ECOZONE_LLM=fake`), which is
NOT Gemini; it shows what the loop and the scorer do without a model. The live Gemini run is in
`test_live_gemini.py`, behind the `live` marker.
"""

from evalkit.bench import Bench
from evalkit.cases import AreaCases
from evalkit.compare import compare
from evalkit.results import Recorder


def test_fake_llm_vs_greedy_per_case(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    for rc in cases.repair:
        run = bench.repair_search(rc)
        row = compare(bench, rc, run)
        row.update(budget_inr=rc.budget_inr, quick_win_share_pct=rc.quick_win_share_pct, proposer="fake")
        rec.measure("gemini_vs_greedy.fake", rc.id, row, "offline rule proposer, not Gemini; no pass mark")
        # What the planner is told must match what the engine says: AI is reported as better only when it is.
        ai_ok = row["ai_acs"] is not None
        expected = ai_ok and (not row["greedy_valid"] or row["delta"] > 0)
        assert row["reported_gemini_beat_greedy"] == expected, row
        # The chosen plan is never worse than greedy unless greedy itself breaks a rule.
        best = run.result.best
        if row["greedy_valid"]:
            assert best.score >= round(bench.greedy_for(rc).portfolio.result.after.acs, 1) - 1e-9, row


def test_protect_options_with_fake_llm(bench: Bench, cases: AreaCases, rec: Recorder) -> None:
    """Informational: options A, B, C for each Protect parcel (worst change, lower is better). No pass mark."""
    for pc in cases.protect:
        run = bench.protect_search(pc)
        options = run.result.options or []
        rec.measure(
            "protect_search.fake",
            pc.id,
            {
                o.key: {
                    "worst_change": o.candidate.score,
                    "risk_label": o.candidate.risk.label if o.candidate.risk else None,
                    "floor_area_pct": o.candidate.floor_area_pct,
                }
                for o in options
            },
            "offline rule proposer, not Gemini",
        )
        assert [o.key for o in options] == ["A", "B", "C"]
