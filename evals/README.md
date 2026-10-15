# evals/

Evaluation harness. Lane: **D/A** for engine and agent tests respectively.

pytest engine tests (determinism, range, direction, shadow geometry, ventilation guard, budget), scripted agent evals (grounding violations, tool-use order, design-search rules, Gemini vs. greedy), and the heat-check validation (`pipeline/validate.py`, Spearman correlation against held-out Landsat surface temperature). Results write to the `eval_results` BigQuery table and to `REPORT.md`, which feeds the README and the deck — never report a target before it is measured.

Not yet implemented. Full test list: [../docs/DESIGN.md](../docs/DESIGN.md#c7-evaluation-harness), [../docs/PLANNING.md](../docs/PLANNING.md#tests).

**Rules:** [RULES.md](RULES.md) for this folder, on top of [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md).
