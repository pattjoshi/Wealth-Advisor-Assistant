# Phase 3 — Agents, graph and CLI (MVP) — Interview Notes

## 1. What was built

This is the "safety point" phase — covers **R3, R4, R5, R6, R10**, the heart of the assignment:

- `graph/state.py` — `WealthAdvisorState`, the one shared, typed state object.
- `agents/base.py` — `BaseAgent` + a `trace_entry()` helper shared by every agent.
- `agents/data_fetcher.py` — `DataFetcherAgent`: loads client data + CRM profile via Phase 2's tools, builds the data-quality report, sets `status="failed"` on unusable data (the fail-safe trigger).
- `tools/portfolio_metrics.py` — `PortfolioMetricsTool`: allocation, holding weights, cash, a rough monthly-expense estimate, liquidity in months.
- `tools/anomaly_detection.py` — `AnomalyDetectionTool`: all **ten** deterministic checks from `planning.md` §4.5 (transaction, trend, and risk signals), severity scoring, a risk score.
- `agents/analyzer.py` — `AnalyzerAgent`: orchestrates the two tools above, nothing deterministic lives in the agent itself.
- `agents/insight.py` — `InsightAgent`: template-only narrative (no LLM yet — that's Phase 5), sorted by severity.
- `graph/orchestrator.py` — `route()`: rule-based router, max-step guard, fail-safe short-circuit.
- `graph/builder.py` — assembles the LangGraph `StateGraph` (hub-and-spoke: every agent returns to the router).
- `schemas/report.py` — `AdvisoryReport`, the structured JSON output (R10).
- `cli.py` — `python -m wealth_advisor.cli run --client <id> [--simulate-crm-failure]`.
- 35 new tests (unit + integration), on top of Phase 1/2's 33 — 68 total.

## 2. Approach used and why

The whole phase is built around one rule: **the deterministic math lives in tools, the agents only orchestrate tool calls.** `AnalyzerAgent` is about 50 lines and contains zero anomaly-detection logic itself — it calls `PortfolioMetricsTool`, then `AnomalyDetectionTool`, and assembles the result. This is deliberate: it means the hard, testable logic (ten anomaly checks, severity scoring) can be unit-tested with plain Pydantic objects and no graph, no LangGraph, no agent machinery involved at all — which is exactly what `test_anomaly_detection.py` does.

The router (`route()`) is a pure function of state — no side effects, no LLM, fully unit-testable in isolation (`test_orchestrator.py`). It reads which agent names appear in `trace` to know what's already run, and returns the name of the next stage. This makes the hub-and-spoke pattern from `planning.md` concrete: every agent node, after running, goes back through this same router function, which decides what happens next — the agents never decide their own successor.

Before writing a single test, I ran the CLI against all 5 Phase 1 mock clients by hand and checked the output line by line: client_002 produced *exactly* the four anomaly types in `expected_anomalies.json` (no more, no less), client_001 produced zero false positives, and client_005 failed cleanly with a readable error and exit code 1 — no stack trace. Only after confirming that did I lock the behavior in as regression tests. This order matters: it's much easier to design a check correctly by watching it run on real data than to guess thresholds and hope the tests pass.

## 3. Technology used and why

| Choice | Why | Alternative considered |
|---|---|---|
| Robust (median/MAD) z-score for "unusual amount" | Resistant to one outlier skewing the baseline — a regular mean/stdev z-score gets dragged by the very outlier you're trying to detect | Simple mean + standard deviation — breaks down with small, skewed samples like a client's transaction history |
| Burst-window detection for "spending spike" (N transactions within a rolling window) instead of month-over-month totals | Doesn't depend on which calendar month a transaction happens to fall into — robust regardless of how the mock data's dates are distributed | Month-vs-rolling-average comparison (as literally worded in `planning.md`) — tried first, but produced false positives on the "clean" client purely from random date-to-month assignment; the burst-window version catches the same real pattern (several same-category charges close together) without that fragility |
| LangGraph conditional edges with one router function reused at every node (`set_conditional_entry_point` + `add_conditional_edges`) | One source of truth for "what happens next," testable without running the graph at all | A separate `if/elif` chain hand-rolled per node — more code, same logic duplicated per node, harder to keep in sync |
| `step_count` incremented by a generic wrapper (`_count_step`) around every agent node | The max-step guard works for *any* future node without each agent remembering to increment it itself | Each agent incrementing `step_count` manually — one forgotten increment breaks the loop guard silently |

## 4. Alternative approaches considered

- **Put anomaly detection logic directly inside `AnalyzerAgent`.** Rejected — it would mean testing ten statistical checks through the full agent/tool machinery instead of as plain functions, and it would violate the `agents → tools → services` dependency rule from `CLAUDE.md` that the whole project is built around.
- **Skip the "unusual_category" and "income_drop" checks since the mock data barely exercises them.** Rejected — both are in `planning.md`'s required list of ten checks, and skipping a check to avoid writing its honest "not enough data" path would be worse than showing exactly what a real system does when it doesn't have enough signal: skip the check and say so (`income_drop`), or — for `portfolio_drawdown`, which the schema genuinely cannot support without historical snapshots — skip it entirely and document the limitation rather than fabricate a proxy metric.
- **Let the Orchestrator route based on an LLM's judgment of "is the data good enough."** Rejected on purpose, per `planning.md`'s locked decision: routing is rule-based so it's free, predictable, and testable without touching an API.

## 5. Expected interview questions

**Q: Walk through what happens end-to-end when I run `python -m wealth_advisor.cli run --client client_002`.**
A: The CLI builds the tools and agents, creates a fresh state, and hands it to the compiled graph. The router sees an empty trace and sends it to `DataFetcherAgent`, which loads the client JSON and CRM profile and returns an update. The router sees `data_fetcher` is done and sends it to `AnalyzerAgent`, which computes portfolio metrics then runs all ten anomaly checks — for client_002 that's four findings (large transfer, duplicate payment, spending spike, concentration) plus a risk score. The router then sends it to `InsightAgent`, which turns those findings into a sorted, plain-English narrative. Finally the router sends it to `finalize`, which marks the run `completed`, and the CLI prints the whole thing as one JSON report.
*Real-world example:* like an assembly line where each station (data intake, inspection, report writing) does its one job and hands the product to a dispatcher, who decides which station it goes to next based on what's already been done to it — no station decides its own next step.

**Q: Why does `AnalyzerAgent` contain almost no logic of its own?**
A: Because all the real work — computing metrics, running the ten checks — is already built as standalone tools that don't need an agent, a graph, or even LangGraph installed to test. The agent's only job is "call tool A, then tool B, handle a tool failure gracefully, package the result." That's a thin, boring, easy-to-get-right layer on top of logic that's already been proven correct in isolation.
*Real-world example:* a restaurant manager doesn't cook the food themselves — they tell the kitchen (the tools) what to make and pass the finished plates to the server (the next step). The manager's job is coordination, not cooking.

**Q: Why did you switch the "spending spike" check from "this month vs. the rolling average" (as the plan originally described) to a rolling time-window burst check?**
A: I tried the month-based version first, ran it against the actual generated mock data, and found it produced a false alarm on the "clean" client — purely because of which calendar month a handful of random transactions happened to land in, not because of any real pattern. The window-based version asks a more direct question — "are several same-category charges clustered close together in time?" — which is actually what a spending burst *is*, and it doesn't care about month boundaries at all. I verified this by re-running against all 5 mock clients and confirming client_001 stayed at zero findings while client_002 still caught its seeded spike.
*Real-world example:* if you're trying to catch someone making 5 purchases in one afternoon, checking "did they spend more this calendar month than last" is the wrong question if that afternoon happens to straddle the 1st of the month — you'd miss half of it in each month's bucket. Looking at a rolling window instead doesn't have that blind spot.

**Q: How does the max-step guard actually prevent an infinite loop?**
A: Every agent node is wrapped by `_count_step`, which increments `state["step_count"]` after the node runs, regardless of what the agent itself returns. The router checks that count first, before anything else — once it hits `MAX_STEPS`, the router returns `"finalize"` no matter what state the run is in. So even if a future phase adds a loop-back edge (like Human Review rejecting and sending the run back to Analyzer) and that loop never resolves, the run is still guaranteed to terminate.
*Real-world example:* like a parking garage ticket machine that will only print you 3 replacement tickets before forcing you to go talk to an attendant — no matter how many times you mess up, the process can't spin forever.

**Q: What's the difference between an agent returning `status: "failed"` and a tool returning `ok: False`?**
A: A tool returning `ok: False` is routine and expected — it's how Phase 2's tools report "that didn't work" without crashing. `state["status"] = "failed"` is a bigger signal set only by `DataFetcherAgent` when the client's data is fundamentally unusable (missing file, broken schema) — it tells the *router* to skip straight to the fail-safe report instead of continuing through Analyzer and Insight on data that doesn't exist. One is a tool-level outcome; the other is a run-level decision.
*Real-world example:* a single failed login attempt is routine (try again); your account being locked after too many failed attempts is a different, bigger state that changes what the whole system does next.

**Q: Why is the CLI's `build_app()` a separate function from `run_client()`?**
A: `build_app()` only wires dependencies (tools, agents, the compiled graph) and returns the graph — it does no actual work. `run_client()` uses that graph to run one client and shape the result into the `AdvisoryReport` schema. Splitting them means the integration tests (`test_graph_run.py`) can call `build_app()` directly with test-specific paths (a temp CRM file, a specific failure rate) without going through argument parsing or the CLI's I/O at all.
*Real-world example:* separating "build the car" from "drive the car to the destination" — you'd want to test-drive the car on a track (tests) without needing to also simulate the dealership paperwork (the CLI's argument parsing).

## 6. Scenario-based questions

**Q: "A new client has an empty `transactions` list." What happens, step by step?**
A: `DataFetcherAgent` still loads the client fine (an empty list is schema-valid) and adds an assumption to the data-quality report: "no transactions on file; transaction-based anomaly checks were skipped." `AnalyzerAgent` still runs `PortfolioMetricsTool` (which works fine on zero transactions — `monthly_expense_estimate` comes back `None`) and `AnomalyDetectionTool` (every transaction-based check just naturally returns no findings on an empty list — no special-casing needed). The run completes normally with portfolio-only findings (concentration, risk mismatch) still possible.
*Real-world example:* like reviewing a brand-new bank account with no transaction history yet — you can still look at today's balance and holdings, you just can't say anything about spending patterns.

**Q: "The CRM is completely down for every client today." Does the whole system go down?**
A: No. Every `DataFetcherAgent` call still succeeds for the client-data half; the CRM half falls back through Phase 2's `CrmTool` to a degraded default profile. `AnalyzerAgent` sees the degraded CRM profile and skips only the one check that needs it (`risk_profile_mismatch`), noting why in the assumptions list. Every other check (all nine others) still runs normally. The run finishes `status: "completed"`, just with one documented gap.
*Real-world example:* like a doctor's office whose insurance-verification system is down — they can still see you, take your vitals, and treat you; they just can't confirm your coverage details until that system is back, and they tell you that plainly instead of turning you away.

**Q: "You need to add an eleventh anomaly check next sprint — say, 'suspicious international transaction.'" Where does the code go, and what has to change in `AnalyzerAgent`?**
A: A new `_check_suspicious_international()` function goes in `tools/anomaly_detection.py`, following the same shape as the other nine (take the client/metrics, return a list of `AnomalyFinding`), and gets one new line added to the list of checks called inside `AnomalyDetectionTool._run()`. `AnalyzerAgent` needs **zero** changes — it already just calls the tool and uses whatever findings come back.
*Real-world example:* adding a new inspection step to a factory's QA checklist doesn't require retraining the line manager — they already just run "the checklist," whatever it currently contains.

**Q: "A reviewer asks: 'why did this specific transaction get flagged?'" Can you answer that from the output alone, without reading the code?**
A: Yes — every `AnomalyFinding` carries an `evidence` dict with the exact numbers that triggered it (e.g. the z-score and category median for "unusual_amount", or the percentage of liquid assets for "large_transfer") plus a human-readable `explanation` string. The JSON report is self-documenting; you don't need to trust a black box or go spelunking through code to understand a specific flag.
*Real-world example:* like a credit score report that doesn't just say "650" — it lists the specific factors ("high credit utilization," "short credit history") that make up that number, so you can check and challenge it.

**Q: "Someone wants the system to handle 10,000 clients overnight instead of one client interactively." What would you change, and what wouldn't need to change?**
A: The CLI/`run_client()` layer would change — you'd batch client IDs and likely run them concurrently or via a queue instead of one `argparse` invocation at a time, and you'd probably want a progress log. But `AnalyzerAgent`, the anomaly checks, the tools, and the graph itself wouldn't need to change at all — they're already designed to process exactly one client's state per invocation, with no global or shared mutable state between runs, so running many of them in parallel is safe by construction.
*Real-world example:* a single ATM transaction's logic doesn't need to change to support a bank running millions of ATMs simultaneously — what changes is the orchestration layer deciding how many run at once, not the logic inside any one transaction.
