# engine/

Deterministic scoring engine, pure Python, no network calls. Lane: **D**.

The only place a score is computed: `AreaModel` in memory, shadow geometry, the four indices (VCI, HEI, GCS, PSS), the five interventions, incremental area rescoring, Repair priority and ACS, the greedy baseline, and driver tags. Agents and the API call this through tools or routes — it never calls out to Gemini or the network, and it must stay deterministic (see [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md), rule 2).

Not yet implemented. Planned module layout and formulas: [../docs/DESIGN.md](../docs/DESIGN.md#c2-scoring-engine), [../docs/PLANNING.md](../docs/PLANNING.md#scoring-engine).
