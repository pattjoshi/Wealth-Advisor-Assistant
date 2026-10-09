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

**Q: Walk through exactly what happens when `CrmTool.execute()` is called for a client whose CRM record exists, but the mock CRM is returning failures on every attempt.**
A: First it tries the CRM up to 3 times, waiting a little longer between each try (that's the "retry" step). If all 3 fail, it gives up on the live CRM and checks: "Do I already have this person's data saved from an earlier successful call?" If yes, it hands that back. If no, it builds a safe, generic default profile and clearly labels it `"degraded"` so nobody downstream mistakes it for fresh data. Either way, the function returns normally — it never crashes.
*Real-world example:* think of calling a bank's customer service line. If the first person can't help, you get transferred (retry). If nobody picks up after 3 transfers, the bank doesn't hang up on you — they say "let us pull up your last known file" (cache) or "here's our standard new-customer form" (default), and they tell you honestly which one you're getting.

**Q: Why does `BaseTool.execute()` catch `Exception` broadly instead of a specific exception type?**
A: Because this one function is the *only* safety net every tool gets, and tools can fail in many different ways we can't all predict in advance (a bad network call, a bug in someone's new tool, a file that doesn't exist). Catching broadly here means "whatever goes wrong, turn it into a tidy `ToolResult(ok=False, ...)` instead of letting the program crash." It's a deliberate trade-off: normally catching "any error" is considered sloppy, but here it's the one designated place meant to do exactly that, so every other part of the code doesn't have to.
*Real-world example:* it's like the circuit breaker box in your house — one single component whose entire job is "something went wrong somewhere in the wiring, cut the power safely" rather than every lamp and socket needing its own separate safety mechanism.

**Q: What's the difference between what `with_retry` solves and what `CircuitBreaker` solves — why do you need both?**
A: `with_retry` handles *short, temporary* glitches — try again almost immediately, it'll probably work. `CircuitBreaker` handles the case where something is *properly broken*, not just glitchy — after several failures in a row, it stops even trying for a while, because hammering a dead service with retries just wastes time and makes things worse. Retry is "try again, it's probably fine." Circuit breaker is "stop wasting effort, this is actually down."
*Real-world example:* if you call a friend and they don't pick up, you might call again in a minute (retry). But if you've called 10 times in a row with no answer, you stop dialing and just wait a while before trying again (circuit breaker) — you don't keep redialing nonstop.

**Q: Why is `ClientDataTool` so thin compared to `CrmTool`?**
A: Because all the hard work — reading the file, checking it matches the expected format, writing a clear error message — was already built in Phase 1 (`ClientProfile.from_file`). `ClientDataTool` doesn't repeat that work; it just wraps it so that, same as every other tool, it returns a `ToolResult` instead of raising an error. `CrmTool` is bigger because it also has to deal with a CRM that might be slow, down, or flaky — problems `ClientDataTool` doesn't have, since it's just reading a local file.
*Real-world example:* it's the difference between photocopying a document you already have (quick, thin wrapper) versus calling an external supplier who sometimes doesn't answer the phone (you need a backup plan, which takes more code).

**Q: How would you swap `MockCrmService` for a real CRM API client without touching `CrmTool`?**
A: Write a new class, say `SalesforceCrmService`, that has the exact same method signature: `get_profile(client_id) -> dict`. As long as it returns data in the same shape and raises `CrmServiceError` on failure, you can hand an instance of it to `CrmTool` instead of `MockCrmService`, and nothing in `CrmTool` — the retry, the circuit breaker, the fallback logic — needs to change at all.
*Real-world example:* like swapping the engine in a car as long as the new one bolts onto the same mounts and connects to the same pedals — the rest of the car doesn't need to be redesigned.

**Q: What would you change about the timeout implementation if this were an async codebase?**
A: Instead of running the blocked call on a separate thread and waiting for it (`concurrent.futures`), I'd use `asyncio.wait_for(coroutine, timeout=seconds)`, which is the native async way to time out a call without needing an extra thread at all. It's simpler and lighter-weight in an async codebase — but this project deliberately stays synchronous (see CLAUDE.md), so the thread-based approach is the right tool for *this* codebase specifically.

## 6. Scenario-based questions

**Q: "The CRM comes back up after being down for 10 minutes, but `CrmTool` keeps returning degraded profiles." Why, and what fixes it?**
A: The circuit breaker opened after enough failures and is waiting out its `reset_timeout` (30 seconds by default in this code) before it lets another real attempt through. If the CRM has genuinely recovered, the very next call after that timeout window will succeed and the breaker will reset itself automatically — no manual restart needed. If it's been way longer than 30 seconds and it's still degraded, that points to a different bug (maybe the cache is stale, or the client was never cached in the first place).
*Real-world example:* like a smoke alarm that, once triggered, stays in "alarm mode" for a short cooldown before it'll let itself be reset — it doesn't instantly trust that the smoke is gone.

**Q: "A client calls the CRM tool for the same client_id twice in a row — first call succeeds, second call's CRM request fails." What happens, and why is that the right behavior?**
A: The second call falls back to the profile cached from the first successful call, and returns it marked `status="ok"` (not degraded) — because it genuinely is the real data, just not freshly re-fetched. This is the right call for a wealth advisor tool because showing an advisor "yesterday's accurate profile" is far more useful than showing them an error or a blank screen in the middle of a client meeting.
*Real-world example:* like a weather app that can't refresh right now — it shows you the last data it successfully pulled, labeled with "as of 10 minutes ago," instead of just showing a blank error screen.

**Q: "Someone wants retries to also happen on `TimeoutError`, not just `CrmServiceError`." What's the change, and what's the risk?**
A: Small change — add `ToolTimeoutError` to the tuple of exception types passed into `with_retry(exceptions=(...))`. The risk: timeouts often mean the other side is *overloaded*, not just unlucky — so retrying aggressively can pile on more load and make things worse, the opposite of what you want. You'd want to keep the retry count low and the backoff delay longer specifically for timeout errors.
*Real-world example:* if a restaurant kitchen is already backed up and slow, customers all re-ordering immediately when their food doesn't arrive just makes the backlog worse — sometimes the right move is to wait longer before asking again, not sooner.

**Q: "A teammate adds a new tool that calls a slow external pricing API and forgets to wrap it in `with_timeout`." What actually happens today?**
A: Nothing in the architecture forces every tool to use a timeout — `with_timeout` is available but opt-in, not automatic. So if that teammate's tool call hangs, the whole run hangs with it; `BaseTool.execute()` only protects against *raised exceptions*, not calls that never return at all. This is a real gap worth flagging honestly rather than pretending it's already covered — the fix would be enforcing a default timeout at the `BaseTool` level itself, so no tool can opt out by accident.
*Real-world example:* it's like having a seatbelt in the car that works great — but only if the driver remembers to put it on; nothing stops them from forgetting.

**Q: "You need to add rate limiting (max N calls per second) to the CRM tool." Where would that logic go?**
A: As another layer in `tools/resilience.py`, alongside retry/timeout/circuit-breaker (e.g. a `with_rate_limit` decorator), then applied inside `CrmTool._fetch_with_retry` the same way the retry decorator already is. It stays out of `MockCrmService` (that's the raw implementation) and out of `CrmTool`'s core fallback logic — it's a separate, reusable cross-cutting concern, same pattern the other three already follow.
*Real-world example:* like adding a new type of checkpoint (a ticket gate) alongside existing checkpoints (security, boarding pass scan) at an airport — same lane, same pattern, one more independent check in the sequence.
