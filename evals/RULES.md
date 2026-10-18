# evals/ rules

Cross-package tests that need the real bundle or live Gemini, and the report that the README and deck quote. Everything in [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md) applies. Per-package unit tests live in each package's `tests/`, not here.

## Layout

```
evals/
  cases.yaml          fixed cases per area (budgets, direction sites, Protect parcels); changes only by PR
  conftest.py         bundle choice, session workbench, outcome rows
  evalkit/            bundle choice, cases loader, engine adapter, comparison, JSONL recorder
  test_determinism.py test_range.py test_direction.py test_ventilation.py test_budget.py
  test_gemini_vs_greedy.py   offline rule proposer ("fake" LLM): win, tie or loss per case with both ACS values
  test_live_gemini.py        live Gemini, marker `live`, skipped without ECOZONE_LLM=gemini and Vertex settings
  test_speed.py       rescore, shadows, greedy and search timings against ENGINEERING_RULES.md §8
  report.py           runs the evals and writes REPORT.md from the rows
  REPORT.md           generated, committed
  results/            local run rows (JSONL); only final.jsonl is committed
  heat_check/         README.md and `data/<area>_block_lst.csv` (+ `.meta.json`) made by `pipeline heat-check`; `test_heat_check.py` reads them (heat index vs Landsat surface temperature on the held-out blocks, no pass mark; skips with the command when the CSV is missing)
  tests/              unit tests of the heat-check statistics, the eval on a synthetic table and its report section (run by `make py-check`, not part of the report)
```

Still to come: a BigQuery sink for the rows. The heat check code is built and tested offline; its result is in REPORT.md only once the live Earth Engine export has been run and its CSV committed.

## Rules

- **Measured, never claimed.** A number goes into REPORT.md, the README or the deck only if an eval produced it, with the commit SHA, bundle version and date.
- Every run writes rows (`test, subject, result, value, run_at, commit, bundle_version`) to a local JSONL under `results/`; the BigQuery `eval_results` sink is not wired yet.
- A failing eval is a finding. Do not weaken the test or tune the engine to pass it: report it with the case, the values and the cause, and mark it `xfail` with a reason only once the cause is understood.
- The search evals use the offline rule proposer unless run with the `live` marker; a table from the rule proposer is never labelled Gemini.
- Gemini vs greedy is reported as win, tie or loss per test case, with both ACS values. There is no pass mark.
- Tuning uses the `tune` split only; reported results use `test` (read from `tune_blocks`/`test_blocks` in meta.json when the pipeline writes them, else the `split` column of blocks.parquet).
- Fixed test cases (areas, budgets, parcels, proposals) are listed in `evals/cases.yaml` and change only by PR.
