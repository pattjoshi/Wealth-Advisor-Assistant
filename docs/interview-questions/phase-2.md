# Phase 2 — Tool layer and mock CRM — Interview Notes

## 1. What was built

Covers **R7** (tool usage abstraction), **R8** (error handling), and **E3** (failure injection):

- `tools/base.py` — `BaseTool` (Template Method: `execute()` always validates → runs → times → converts any exception into a failed `ToolResult`) and `ToolResult(ok, data, error, source, latency_ms)`.
- `tools/registry.py` — `ToolRegistry`, a name-keyed lookup so agents receive tools by dependency injection rather than importing implementations directly.
- `tools/resilience.py` — `with_retry` (exponential backoff via `tenacity`), `with_timeout` (thread-based, works on sync blocking calls), `CircuitBreaker` (closed/open/half-open).
- `services/mock_crm.py` — `MockCrmService`: random latency + a configurable failure rate (`CRM_FAILURE_RATE`), raising `CrmServiceError` — the "raw implementation" agents never see directly.
- `tools/crm.py` — `CrmTool`: wraps the mock CRM with retry + circuit breaker, and the fallback chain **live → last cached profile → default profile marked `status="degraded"`**. Added a `status` field to `CrmProfile` (Phase 1 schema) to carry that signal.
- `tools/client_data.py` — `ClientDataTool`: wraps `ClientProfile.from_file` (Phase 1) behind the same tool interface, so a schema validation error becomes a failed `ToolResult`, not a raised exception.
- `config.py` — `pydantic-settings` `Settings`, env prefix `WA_`, `OPENAI_API_KEY` as the one unprefixed exception (matches `.env.example`).
- 33 unit tests: tool base (success / validation failure / exception never raised), registry, retry/timeout/circuit-breaker, mock CRM (success / unknown client / always-fails), `CrmTool` (success / retry-then-success / total failure → degraded / cache-before-default), `ClientDataTool` (valid / malformed / missing argument).

## 2. Approach used and why

The one invariant this phase exists to prove: **a tool call result is always a `ToolResult`, never a raised exception** — reaching an agent. That's enforced structurally, not by convention: `BaseTool.execute()` is a Template Method that wraps `_run()` in a single `try/except Exception`, so a subclass physically cannot leak an exception past `execute()` even if it forgets to handle an edge case itself. This is the mechanism behind R8 ("gracefully handle failures... ensure system stability").

`CrmTool`'s fallback chain is deliberately layered as three independent concerns: retry (tenacity, for transient failures), a circuit breaker (to stop retrying a CRM that's clearly down, not just flaky), and an application-level fallback (cache, then a default profile). Each layer is tested in isolation (`test_resilience.py`) and then in combination (`test_crm_tool.py`), because the interesting bugs in resilience code are usually in how the layers compose, not in any one layer alone.

`ClientDataTool` is intentionally thin — it adds zero new error handling of its own, because `ClientProfile.from_file()` (Phase 1) already raises a single typed exception (`ClientDataValidationError`) with a clear message. The tool layer's job here is just to make that exception non-fatal to the caller, which `BaseTool.execute()` already does generically. This is the payoff of getting Phase 1's error type right: Phase 2 needed zero CRM-specific error-formatting code for the client-data path.

## 3. Technology used and why

| Choice | Why | Alternative considered |
|---|---|---|
| Template Method (`BaseTool.execute()` / `_run()`) | Error handling lives in exactly one place; every tool gets it for free and can't opt out | Each tool implementing its own try/except — error handling quality would vary per tool |
| `tenacity` for retry | Battle-tested, declarative (`stop_after_attempt`, `wait_exponential`, `retry_if_exception_type`), already a project dependency | Hand-rolled retry loop — more code, easy to get backoff math wrong |
| Thread-based timeout (`concurrent.futures`) | Works for ordinary synchronous blocking calls without introducing `asyncio` into a project that CLAUDE.md deliberately keeps sync | `signal.alarm` — Unix-only, doesn't work in threads; full `asyncio` rewrite — large scope increase for one cross-cutting concern |
| Hand-rolled `CircuitBreaker` (closed/open/half-open) | ~30 lines, no new dependency, behavior is easy to explain and test exhaustively | `pybreaker` — a well-known library, but adding a dependency for 30 lines of well-understood logic isn't worth it here |
| `status: Literal["ok", "degraded"]` added to `CrmProfile` | Lets the Analyzer/Insight agents (Phase 3+) see *why* a profile might be thin, without string-sniffing `advisor_notes` | Encoding degraded-ness only in free text — works for a human reading logs, not for code making decisions |

## 4. Alternative approaches considered

- **Put retry/timeout/circuit-breaker logic inside `MockCrmService` itself.** Rejected — that conflates "what the CRM does" with "how we tolerate the CRM failing," and would mean every future real CRM adapter has to reimplement resilience instead of getting it for free from `CrmTool`.
- **Mark degraded status via `ToolResult` instead of the `CrmProfile` schema.** Considered, since `ToolResult` is the generic cross-cutting wrapper. Rejected because `ToolResult.source` is fixed to the tool's own name (identifies *which tool ran*, not the *data's provenance*), and overloading it with per-call dynamic state would mean mutable instance state on tool objects — a bigger structural change for a narrower, CRM-specific concern that the schema already models cleanly.
- **Use a real circuit-breaker library (`pybreaker`).** Rejected for this scope — the behavior needed (count failures, open, wait, half-open) is small and fully covered by `test_resilience.py`; a dependency should earn its keep.

## 5. Expected interview questions

- Walk through exactly what happens when `CrmTool.execute()` is called for a client whose CRM record exists, but the mock CRM is returning failures on every attempt.
- Why does `BaseTool.execute()` catch `Exception` broadly instead of a specific exception type?
- What's the difference between what `with_retry` solves and what `CircuitBreaker` solves — why do you need both?
- Why is `ClientDataTool` so thin compared to `CrmTool`?
- How would you swap `MockCrmService` for a real CRM API client without touching `CrmTool`?
- What would you change about the timeout implementation if this were an async codebase?

## 6. Scenario-based questions

- **"The CRM comes back up after being down for 10 minutes, but `CrmTool` keeps returning degraded profiles."** Given `CircuitBreaker`'s `reset_timeout`, walk through why, and what config value controls when it recovers.
- **"A client calls the CRM tool for the same client_id twice in a row — first call succeeds, second call's CRM request fails."** What does the second call return, and why is that the *right* behavior for a wealth advisor product (vs., say, returning an error)?
- **"Someone wants retries to also happen on `TimeoutError`, not just `CrmServiceError`."** What's the one-line change, and what's the risk of retrying on a broader exception set?
- **"A teammate adds a new tool that calls a slow external pricing API and forgets to wrap it in `with_timeout`."** What actually happens today if that API hangs — does anything in this architecture protect against it, or is that still a gap?
- **"You need to add rate limiting (max N calls per second) to the CRM tool."** Where would that logic go, following the same layering this phase already established?
