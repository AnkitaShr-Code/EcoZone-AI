# evals/ rules

Cross-package tests that need the real bundle or live Gemini, and the report that the README and deck quote. Everything in [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md) applies. Per-package unit tests live in each package's `tests/`, not here.

## Layout

```
evals/
  agents/      live Gemini runs: grounding, tool order, Gemini vs greedy, design-search rules
  speed/       pytest-benchmark on the real bundle (ENGINEERING_RULES.md §8)
  heat_check/  heat index vs Landsat LST on held-out blocks (only if Earth Engine lands)
  report.py    writes REPORT.md from the latest eval_results rows
  REPORT.md    generated, committed
```

## Rules

- **Measured, never claimed.** A number goes into REPORT.md, the README or the deck only if an eval produced it, with the commit SHA, bundle version and date.
- Every run writes rows to BigQuery `eval_results` (`test, subject, result, value, run_at, commit, bundle_version`) and can also write a local JSONL when offline.
- Gemini vs greedy is reported as win, tie or loss per test case, with both ACS values. There is no pass mark.
- Tuning uses the `tune` split only; reported results use `test`.
- Fixed test cases (areas, budgets, parcels, proposals) are listed in `evals/cases.yaml` and change only by PR.
