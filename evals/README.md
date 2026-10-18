# evals/

Evaluation harness. Lane: **D/A** for engine and agent tests respectively.

pytest engine tests (determinism, range, direction, shadow geometry, ventilation guard, budget), scripted agent evals (grounding violations, tool-use order, design-search rules, Gemini vs. greedy), and the heat-check validation (`test_heat_check.py`, Spearman correlation against held-out Landsat surface temperature). Results write to the `eval_results` BigQuery table and to `REPORT.md`, which feeds the README and the deck — never report a target before it is measured.

Implemented (WP10 subset): determinism, range, direction, ventilation guard, budget, Gemini vs greedy (offline rule proposer; live Gemini behind the `live` marker) and speed, all on the real bundle with the tiny fixture as the CI fallback. The heat check (`test_heat_check.py`, see [heat_check/README.md](heat_check/README.md)) is built but needs its Earth Engine export (`pipeline heat-check`) before it reports; until then it skips and REPORT.md says it was not run. Not yet: the BigQuery `eval_results` sink (rows go to a local JSONL for now). Full test list: [../docs/DESIGN.md](../docs/DESIGN.md#c7-evaluation-harness), [../docs/PLANNING.md](../docs/PLANNING.md#tests).

**Rules:** [RULES.md](RULES.md) for this folder, on top of [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md).

## Run

```
uv run pytest evals -m "not live"            # offline evals; on the Deccan bundle this takes a few minutes
uv run python evals/report.py                # the same run, then writes REPORT.md from its rows
uv run python evals/report.py --from evals/results/final.jsonl   # rebuild REPORT.md from saved rows
ECOZONE_LLM=gemini uv run pytest evals -m live                   # live Gemini (Vertex credentials needed)
```

The bundle is `ECOZONE_EVAL_BUNDLE` if set (an invalid path is an error), else `data/areas/deccan/v1` in this checkout or
in the main checkout, else the tiny fixture. The pytest header and REPORT.md say which one ran, so the suite never
silently does nothing. Cases are in [cases.yaml](cases.yaml).
