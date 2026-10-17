# agents/ rules

Package `ecozone_agents`. ADK agents on Vertex AI Gemini: the four task agents, the shared search loop, tool wrappers and the output guard. Everything in [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md) applies; this file adds what is specific here. Agent and tool contracts: [../docs/PLANNING.md](../docs/PLANNING.md#gemini-agents-and-tools).

## Layout

```
agents/src/ecozone_agents/
  config.py          AgentSettings: LLM mode, Vertex project/location, model ids, round limits, timeouts (from env)
  ports.py           EnginePort, ModelClient, Proposer, Writer protocols; Emit and the event union
  runner.py          AgentsRunner (search, explain) and build_runner(); routes by request mode in code
  search.py          the one generic loop: Proposer (model) → Scorer (code) → Judge (code), plus Scored
  repair.py          RepairMode: greedy baseline, portfolio scoring and validity, rejected options, result
  protect.py         ProtectMode: design ranges, floor-area rules, options A/B/C, trade-off text, result
  catalog.py         sites and parcels as the agents see them (from engine layer and single_site)
  llm.py             prompts loader, response schemas, GeminiClient (google-genai, Vertex), LlmProposer, LlmWriter
  offline.py         RuleProposer for ECOZONE_LLM=fake
  facts.py           the engine values an explanation may cite (shown to the writer, used by guard and template)
  explain.py         writer → guard → one retry → template, with the explain timeout
  guard.py           output guard rules and grounding
  templates.py       plain templates filled from facts
  text.py            number formats and plain-language labels (match app/src/lib/format.ts and meta.ts)
  to_contract.py     engine ↔ contract conversions and rounding
  fake_llm.py        ScriptedModel and ScriptedProposer for tests
  prompts/           one versioned .md prompt per proposer mode and for the writer
```

## Rules

- **Routing is code.** `runner.py` picks Repair or Protect from the request's `mode`. There is no LLM orchestrator.
- **No ADK.** The loop and the writer are plain asyncio over `google-genai` (reasons in ENGINEERING_RULES.md §2). Model access goes through the `ModelClient` protocol, so an ADK-backed client could be added without touching the loop.
- **The engine is the only place a number is made.** Agents call the engine through `EnginePort` (sync, CPU-bound, so always via `asyncio.to_thread`) and never compute a score, cost or risk. Comparisons use the engine's raw values; planner-facing values are rounded in `to_contract.py`.
- **One search loop.** `search.py` serves Repair portfolios and Protect designs. Mode-specific behaviour is passed in as a `SearchMode` (candidate schema, validity rule, threshold, brief, result), never forked into a second loop.
  - Proposer: Flash tier model, structured output (`response_schema` = the candidate list), sees compact JSON briefs (ids, costs, single-site gains, best so far), never geometry.
  - Scorer: code. It calls `rescore` for each candidate, drops invalid ones with a plain-language reason (over budget, below the quick-win share, ventilation fail, unknown or repeated site, quantity out of range, outside the design ranges, floor-area rule), and emits one `candidate` event each. Repeats of an earlier candidate are skipped.
  - Judge: code. It stops at the round limit, when no objective improved by more than the mode threshold (never before round 2, so the planner always sees a refinement), or at the time limit (best so far).
  - The greedy baseline is computed first and emitted as the `baseline` event. Gemini "beats" greedy only with a strictly higher score; otherwise the result is greedy and says so. Protect's baseline is the proposal as entered (option A).
- **Prose uses the Pro tier model** with the output parts fixed by PLANNING.md: diagnosed issue, primary drivers, options and trade-offs, recommendation, data caveats.
- **Prompts are files**, versioned by filename suffix, with no hard-coded scores or example numbers (a test checks this).
- **Fail soft.** A proposer error or timeout ends the run with the best scored result and an `error` event. A stop (task cancellation) emits `done` with the best so far and the template text, then exits. If the writer fails or times out the template is used. If greedy itself cannot run, the run ends with an `error` event only.
- **Credentials.** Application Default Credentials only. There is no API key setting. `ECOZONE_LLM=fake` makes no cloud calls at all. Tests that call Gemini are marked `@pytest.mark.cloud`.
- **Fake mode labels.** The contract has no "rule" source, so offline proposals carry `source="gemini"`. Use `ECOZONE_LLM=fake` for development and demos of the UI only.

## Output guard

Runs on every model answer that reaches the planner.

1. Extract every number from the text (integers, decimals, percentages, rupee amounts in lakh and crore, written in digits).
2. Build the allowed set from this turn's tool results and planner input, including their displayed forms (1-decimal scores, ₹ lakh with 1 decimal, whole percentages).
3. Also allowed: round counts up to the round limit, the reference times (1 pm, 3 pm, 4 pm; 13:00, 15:00, 16:00), the scale "0–100", and list ordinals up to 10. The reference date is allowed because it is in the facts.
4. A number matches when it equals a value in the set after rounding to the digits written (so "64" matches 63.5 and "₹ 9.3 lakh" matches ₹ 9,25,000). The writer is told never to compute differences, sums or percentages; one it computes is rejected.
5. Reject on any number not in the set, any forbidden unit (ENGINEERING_RULES.md §7), any approval language, "price" or "market rate" wording, rupee amounts without the planner-input label, driver tags the engine did not return, and site, parcel or block ids that are not in the facts.
6. On rejection, regenerate once with the violations listed. On a second rejection, return the template from `templates.py` filled from engine values. Mark the `Explanation.source` accordingly, emit a `guard` event for each rejection (`fallback` is true on the second), and log the violations. A 20 s timeout on the whole explanation (`ECOZONE_EXPLAIN_TIMEOUT_S`) also ends in the template, with no guard event.

The guard is plain code with its own test table of accepted and rejected texts; extend the table with every false positive or negative found.

## Tests

- CI tests use `fake_llm.py` and a fake engine in `tests/conftest.py` only: loop control flow, invalid-candidate drops, judge stopping, greedy-wins path, cancellation, Protect options, guard table, retry then template fallback, explain timeout.
- Async tests use anyio's pytest plugin (`pytest.mark.anyio`).
- Live evals (`evals/agents/`) are run by hand and report grounding violations, tool order and Gemini vs greedy.
