# agents/ rules

Package `ecozone_agents`. ADK agents on Vertex AI Gemini: the four task agents, the shared search loop, tool wrappers and the output guard. Everything in [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md) applies; this file adds what is specific here. Agent and tool contracts: [../docs/PLANNING.md](../docs/PLANNING.md#gemini-agents-and-tools).

## Layout

```
agents/src/ecozone_agents/
  config.py          model ids, location, timeouts, round limits (from env + settings)
  runner.py          entry points the API calls: run_search(), explain(), write_brief(); routes by task in code
  spatial.py         Spatial Analyst
  repair.py          Repair Planner
  scenario.py        Scenario Analyst
  advisor.py         Planning Advisor
  tools.py           thin wrappers: validate args → engine call → JSON-able result
  search.py          the one generic LoopAgent: Proposer (LLM) → Scorer (code) → Judge (code)
  guard.py           output guard as after_model_callback, plus template fallback
  templates.py       plain templates filled from engine values
  prompts/           one versioned .md prompt per agent and per proposer mode
  fake_llm.py        scripted model for tests
```

## Rules

- **Routing is code.** `runner.py` picks the agent by task (search, explain, brief). There is no LLM orchestrator.
- **Tools never compute.** A tool validates its arguments, calls one engine function, and returns the result unchanged except for conversion to JSON. Business logic in a tool is a review blocker.
- **One search loop.** `search.py` serves Repair portfolios and Protect designs. Mode-specific behaviour is passed in (candidate schema, validity rule, threshold, prompt), never forked into a second loop.
  - Proposer: Flash tier model, structured output (`response_schema` = the candidate list), sees compact JSON summaries (ids, costs, single-site gains, best so far), never geometry.
  - Scorer: a code `BaseAgent`. It calls `rescore` for each candidate, drops invalid ones with a reason (over budget, ventilation fail, floor-area rule, unknown site), and emits one `candidate` event each.
  - Judge: a code `BaseAgent`. It stops after the settings round limit, or when no candidate beats the best by the mode threshold, or at the time limit (best so far).
  - The greedy baseline is computed first and emitted as the `baseline` event. If greedy beats every Gemini candidate, the result is greedy and says so.
- **Prose uses the Pro tier model** (explanations, cooling plan, planning brief, field check lists), with the output parts fixed by PLANNING.md: diagnosed issue, primary drivers, options and trade-offs, recommendation, data caveats.
- **Prompts are files**, versioned by filename suffix, with no hard-coded scores or example numbers that could leak into output.
- **Imagery** observations are structured output with a confidence per field and are always labeled AI-estimated; they never overwrite a data-layer value.
- **Fail soft.** Model errors, timeouts or schema failures end the run with the best scored result and an `error` event. The UI is never left without a result if greedy ran.

## Output guard

Runs on every model answer that reaches the planner.

1. Extract every number from the text (integers, decimals, percentages, rupee amounts in lakh and crore, written in digits).
2. Build the allowed set from this turn's tool results and planner input, including their displayed forms (1-decimal scores, ₹ lakh with 1 decimal, whole percentages).
3. Also allowed: round counts up to the round limit, the reference times (1 pm, 3 pm, 4 pm; 13:00, 15:00, 16:00), the reference date, and list ordinals up to 10.
4. Reject on any number not in the set, any forbidden unit (ENGINEERING_RULES.md §7), or any approval language.
5. On rejection, regenerate once with the violations listed. On a second rejection, return the template from `templates.py` filled from engine values. Mark the `Explanation.source` accordingly, emit a `guard` event, and log the violation.

The guard is plain code with its own test table of accepted and rejected texts; extend the table with every false positive or negative found.

## Tests

- CI tests use `fake_llm.py` only: loop control flow, invalid-candidate drops, judge stopping, greedy-wins path, guard table, template fallback.
- Live evals (`evals/agents/`) are run by hand and report grounding violations, tool order and Gemini vs greedy.
