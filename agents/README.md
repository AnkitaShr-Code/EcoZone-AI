# agents/

Agent layer (Gemini on Vertex AI through `google-genai`). Lane: **A**. Built in WP7.

The API picks the role by route in code: Repair and Protect searches run on one generic loop (`search.py`: Gemini proposer → code scorer that calls the engine → code judge that decides when to stop; `repair.py` and `protect.py` pass in the mode-specific parts), and explanations come from a writer model whose answer the output guard (`guard.py`) checks before it reaches the planner. The model proposes site ids or designs and writes prose; every number comes from the engine. A guard rejection regenerates once, then falls back to a template (`templates.py`).

`AgentsRunner` (`runner.py`) implements the API's `SearchRunner` protocol. `ECOZONE_LLM=fake` swaps Gemini for an offline rule proposer and template text, so the whole app runs without any cloud access once the engine exists.

Design: [../docs/DESIGN.md](../docs/DESIGN.md#c4-agent-layer-gemini-on-vertex-ai-plain-asyncio-code), [../docs/PLANNING.md](../docs/PLANNING.md#gemini-agents-and-tools). Not built yet: the Spatial Analyst (imagery) and the planning brief.

**Rules:** [RULES.md](RULES.md) for this folder, on top of [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md).
