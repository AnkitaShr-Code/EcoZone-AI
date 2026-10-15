# agents/

ADK agent layer (Gemini on Vertex AI). Lane: **A**.

One orchestrator routes to four sub-agents (Spatial Analyst, Repair Planner, Scenario Analyst, Planning Advisor). Repair's portfolio search and Protect's design search both run on the same generic `LoopAgent` (`search.py`: Gemini proposer → non-LLM scorer that calls the engine → non-LLM judge that decides when to stop) — do not fork this into mode-specific loops. Every tool wrapper calls `engine/` and returns its result unchanged; the output guard (`guard.py`) rejects any answer with a number not present in that turn's tool results or planner input, or a forbidden physical unit.

Not yet implemented. Planned agents, tools, and the search loop: [../docs/DESIGN.md](../docs/DESIGN.md#c4-agent-layer-adk-on-vertex-ai-gemini), [../docs/PLANNING.md](../docs/PLANNING.md#gemini-agents-and-tools).

**Rules:** [RULES.md](RULES.md) for this folder, on top of [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md).
