# Phase 4 — Logging and hardening — Interview Notes

## 1. What was built

Covers **R9** (logging), **E6** (PII masking), **E9** (data quality is already honest from Phase 3; this phase makes the *process* that produces it observable too):

- `observability/logging.py` — `structlog` configured for JSON-lines output. Console logs go to **stderr**, never stdout, so the CLI's JSON report stays a single parseable object on stdout. A `mask_pii` processor runs on every log call, recursively redacting `full_name`, `date_of_birth`, `payee`, `advisor_notes` wherever they appear, however deeply nested.
- `observability/trace.py` — `wrap_node()`: wraps every graph node with start/complete/failed logging, per-node timing, step counting, **and the global exception safety net** — any unexpected error inside a node is caught, logged, turned into a state error, and the run still ends cleanly through the normal fail-safe path instead of crashing with a raw traceback.
- `graph/orchestrator.py` — `route()` is now a thin wrapper over a new `decide()` function that returns `(next_node, reason)`, so every routing decision can be logged with *why*, not just *what*.
- `graph/builder.py` — every node now goes through `wrap_node()`; routing goes through `_route_and_log()`.
- `agents/data_fetcher.py` / `agents/analyzer.py` — every tool call is now logged (`tool_call` event: agent, tool, ok, source, latency_ms, error) in addition to being recorded in `trace[]`.
- `cli.py` — calls `configure_logging()` at the top of `run`, using `settings.log_level` / `settings.log_file`.
- 15 new tests (83 total): PII masking (flat, nested, `None`-safe), the exception safety net, routing reasons, and an integration test that runs the real CLI and asserts stdout is *only* the report while the log file has the full structured trail.

## 2. Approach used and why

The hardening piece and the logging piece are really one mechanism, not two: `wrap_node()` does both at once, because the thing that makes a node's unexpected failure *debuggable* (structured logging with timing) is the same wrapper that makes it *survivable* (the try/except). Doing them separately would mean every node needs two decorators applied in the right order instead of one function that gets this right by construction — it's also why this lives in `observability/trace.py` and gets reused by `graph/builder.py` rather than being hand-rolled per node.

I didn't change `route()`'s signature — existing Phase 3 tests call `route(state) -> str` directly, and breaking that would mean touching tests that were already passing for a reason unrelated to this phase. Instead `decide()` is new, `route()` became `return decide(state)[0]`, and the logging wrapper in `builder.py` calls `decide()` directly to get the reason. This is a small but real lesson in incremental design: add the richer function alongside the old one, make the old one delegate to it, don't widen an existing public signature unless you have to.

Before writing a single test, I ran the CLI by hand and inspected stdout, stderr, and the log file separately (`python -m wealth_advisor.cli run --client client_001 > stdout.json 2> stderr.log`) to confirm the stdout/stderr split actually worked — this is the kind of thing that's easy to get subtly wrong (e.g. structlog defaulting to stdout) and would silently break every downstream consumer of the CLI's JSON output if I'd only trusted the code to be correct.

## 3. Technology used and why

| Choice | Why | Alternative considered |
|---|---|---|
| `structlog` with a `JSONRenderer` | One structured log entry per line, trivially greppable/parseable, `run_id` attachable via `.bind()` without threading it through every function signature | Plain `logging` with string formatting — would mean hand-writing JSON or parsing free text later, which defeats the point of "logs for debugging and observability" |
| PII masking as a **global structlog processor**, not a per-call-site habit | Runs on every single log call automatically — a future log line that happens to include `full_name` is still caught, with zero chance of a developer forgetting to redact it manually | A `mask()` helper developers remember to call before logging — relies on discipline, and discipline doesn't scale; the exact kind of thing a finance product can't risk |
| Console logs to **stderr**, not stdout | The CLI's contract is "stdout is exactly one JSON report" (used by `jq`, by tests, by any downstream pipeline); mixing log lines into stdout would silently break that contract | Logging to stdout — simpler to wire, but breaks `python -m wealth_advisor.cli run ... | jq .` the moment logging is turned on |
| `logging.basicConfig(..., force=True)` | Each `configure_logging()` call fully resets handlers — matters for tests (multiple runs with different temp log files in one process) and for any host embedding the CLI more than once | Default `basicConfig` behavior (no-ops if handlers already exist) — would silently keep logging to the *first* test's temp file in every subsequent test, a very confusing bug to chase |

## 4. Alternative approaches considered

- **Catch exceptions inside each agent individually instead of at the node-wrapper level.** Rejected — that's exactly the kind of per-call-site discipline that doesn't scale (same argument as PII masking above). A new agent written next sprint gets the safety net for free just by being registered as a graph node; it doesn't need to remember to wrap its own `run()` in a try/except.
- **Log the full client/CRM payload at the "node_started" event for richer debugging context.** Rejected — more log volume for marginal debugging value, and it's exactly the kind of place PII would leak if the masking processor ever had a gap. Logging stays intentionally thin (ids, tool names, latencies, ok/error) so there's less PII-shaped surface area to protect in the first place; the masking processor is still there as defense-in-depth, not the only line of defense.
- **Use Python's standard `logging` module's built-in JSON formatter instead of `structlog`.** Rejected — `structlog`'s processor pipeline is what makes `mask_pii` and `run_id` binding both trivial and composable; doing the same with stdlib `logging` would mean a custom `Filter` plus a custom `Formatter` working together, more code for the same result.

## 5. Expected interview questions

**Q: Why does the CLI send logs to stderr instead of stdout?**
A: Because the CLI's actual output — the JSON report — has to be something another program can pipe and parse without extra work, like `python -m wealth_advisor.cli run --client client_001 | jq .risk_score`. If log lines were mixed into stdout, that pipe would break the moment logging produced any output, because `jq` would be trying to parse log lines as if they were part of the report.
*Real-world example:* like a printer that prints your document on one tray and spits out its internal diagnostic ("low toner", "jam cleared") on a separate tray — you'd never want diagnostic messages literally printed onto the document you asked for.

**Q: How does the exception safety net actually prevent a crash, step by step?**
A: Every node function is wrapped by `wrap_node()` before it's registered with the graph. Inside that wrapper, the real node function runs inside a `try` block. If it raises *any* exception, the `except` clause catches it, logs it with how long the node ran before failing, appends a readable message to the state's `errors` list, sets `status` to `"failed"`, and returns that as a normal state update — exactly like a successful node would, just with different content. The graph itself never sees an exception; it just sees a state update, same as always, and the router then sends the run straight to `finalize` because `status == "failed"`.
*Real-world example:* like a building's fire suppression system — a fire (exception) inside one room doesn't bring down the whole building; it's contained, logged on the fire panel, and the building's emergency protocol (the fail-safe route) takes over cleanly.

**Q: Why mask PII as a "processor" instead of just being careful about what you log?**
A: Because "being careful" is a human habit, and habits fail under time pressure or when someone new touches the code without reading every rule first. A processor runs on literally every log call, automatically, with no opt-in step — so even a log line added in a rush six months from now, that happens to include a client's name in some dict, gets redacted without the person who wrote it needing to remember to do anything.
*Real-world example:* it's the difference between asking every employee to remember to shred sensitive documents (relies on each person, every time) versus putting a locked shredder bin by every desk that automatically destroys anything dropped in it — the second one doesn't depend on anyone remembering.

**Q: What's actually in a log line right now — walk me through one.**
A: Something like `{"run_id": "...", "agent": "data_fetcher", "tool": "crm_tool", "ok": true, "source": "crm_tool", "latency_ms": 75.79, "error": null, "event": "tool_call", "level": "info", "timestamp": "..."}`. That one line tells you: which run, which agent called which tool, whether it succeeded, how long it took, and when. Multiply that by every tool call and every routing decision in a run, and you have a complete, replayable story of what happened — all without needing to attach a debugger.
*Real-world example:* like an airplane's flight data recorder — not a video of the flight, but enough structured readings (altitude, speed, control inputs, each timestamped) to reconstruct exactly what happened and when, after the fact.

**Q: Why did `decide()` get added instead of just changing what `route()` returns?**
A: Because `route()` already had a contract — "takes state, returns a node name string" — and Phase 3's tests, which were already passing, depend on exactly that. Changing `route()` to return a tuple would have silently broken every existing caller and every existing test. Adding `decide()` as the richer version, with `route()` reduced to `decide(state)[0]`, means old code and old tests keep working unchanged while new code (the logging wrapper) gets the extra information it needs.
*Real-world example:* like adding a new "detailed receipt" option at a checkout instead of changing what the basic receipt already prints — people who were fine with the short receipt aren't suddenly handed more paper than they wanted.

## 6. Scenario-based questions

**Q: "A bug in a future Phase 6 memory-lookup causes an unhandled `sqlite3.OperationalError` inside the Analyzer." What does the user see?**
A: They see a normal JSON report with `"status": "failed"` and an `errors` entry like `"analyzer: unexpected error: <the sqlite error message>"` — not a Python traceback, not a hung process, not a crashed CLI. The log file has a `node_failed` entry with the exact error and how long the node ran before it died. The fix is then just "read the error message," not "reproduce a crash."
*Real-world example:* like a car's dashboard showing a specific warning light ("check engine — code P0300") instead of the engine just silently dying on the highway with no explanation.

**Q: "A compliance reviewer asks: 'can you prove no client names ever hit your log files, going back six months?'" What's your answer?**
A: Yes, structurally — not just "we were careful." Every log call in the codebase goes through the same `structlog.configure()` pipeline, and `mask_pii` is one of the processors in that pipeline, applied to every single log event before it's rendered to JSON, with no code path that bypasses it. You'd point to `test_mask_pii_*` and `test_configure_logging_masks_pii_end_to_end` in the test suite as the proof this isn't just a claim — it's enforced and verified.
*Real-world example:* like being able to show an auditor the actual metal detector at every entrance, not just a sign that says "no weapons allowed" — the control is physical/automatic, not a policy someone has to remember to follow.

**Q: "You need to add a new log field — say, `client_segment` — to every tool_call event." Where does that change go?**
A: One place: `log_tool_call()` in `observability/trace.py`, or the `trace_entry()` call sites in the agents if the field needs to come from agent-level context. Because every tool call already funnels through `log_tool_call(state, entry)`, you don't need to find and update every individual `log.info(...)` call scattered across the codebase — there's exactly one chokepoint for "what does a tool_call log look like."
*Real-world example:* like changing a company's email signature template in one shared template file instead of asking every employee to individually update their own.

**Q: "Running this at scale, someone complains the log file is enormous after a week." What would you change, and what wouldn't need to change?**
A: I'd add log rotation (Python's `logging.handlers.RotatingFileHandler` or `TimedRotatingFileHandler`) in `configure_logging()` — that's a config-level change, swapping `FileHandler` for a rotating one. Nothing about *what* gets logged, the PII masking, or the node-wrapping logic would need to change at all — the volume problem and the content problem are independent, which is exactly why structlog's processor pipeline and the handler configuration are separate concerns in this design.
*Real-world example:* like replacing a small mailbox with a bigger one, or adding a mail-forwarding service, without needing to change what kind of mail gets delivered in the first place.
