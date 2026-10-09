# Phase 5 — LLM insight with cost control — Interview Notes

## 1. What was built

Covers **E1** (one LLM call per run) and **E2** (cost control):

- `llm/base.py` — `LLMClient` ABC + `LLMResponse` dataclass. Every model call in the system goes through this interface.
- `llm/mock_client.py` — `MockLLMClient`: deterministic, offline, zero-cost. Echoes the findings block already in the prompt — grounded by construction. Used automatically when no `OPENAI_API_KEY` is set, and always in tests/CI.
- `llm/openai_client.py` — `OpenAIClient`: thin adapter over the real SDK, `max_retries=0` (retry policy lives one layer up, per `CLAUDE.md`'s "one layer owns the policy" rule).
- `llm/prompts.py` — `build_insight_prompt()`: a compact prompt built only from findings (type, severity, explanation) and the risk score — never raw transactions, never the client's identity (more on why below).
- `llm/cache.py` — `LLMCache`: SQLite-backed, keyed by a hash of `(model, findings, risk_score)`. A second run with identical findings costs zero — no call, no tokens.
- `llm/cost.py` — `estimate_cost_usd()`: a small illustrative pricing table, logged per run.
- `llm/grounding.py` — `numeric_vocabulary()` / `is_grounded()`: the safety guard. Extracts every number from the LLM's output and rejects it if any number isn't traceable to the real findings.
- `agents/insight.py` — rewired: tries the LLM (cache → call → grounding check), falls back to the Phase 3 deterministic template (`render_template_narrative`) on a cache miss that fails to generate, an API error, or an ungrounded result.
- `cli.py` — `build_llm_client()`: OpenAI when a key is configured, `MockLLMClient` otherwise, automatic, no flag needed.
- 33 new tests (116 total).

## 2. Approach used and why

The core design principle carried over from `planning.md`'s locked decision: **the LLM only writes the narrative — it never computes a number.** Every number that can legally appear in the output already exists in the Analyzer's findings before the LLM is ever called. That's what makes the grounding guard possible at all: if the LLM only paraphrases, "does this output only use real numbers" is a checkable, mechanical question, not a judgment call.

I ran the actual CLI by hand before trusting any of this — and it caught two real bugs that unit tests alone wouldn't have caught quickly:

1. **A false-positive grounding rejection.** The first version of the regex-based number extractor matched the digits inside `client_002` as the number `2`, which wasn't in the findings vocabulary, so every single run failed the grounding check and silently fell back to the template — the LLM path never actually worked. Running the CLI and reading the `fallback_reason` field in the output surfaced this immediately; a unit test with hand-picked fixture text might never have hit that exact failure mode.
2. **A cross-client identity leak via the cache.** `client_001` and `client_004` both have zero anomalies, so they hash to the same cache key — by design, since the cache is keyed by findings, not by client, to maximize reuse. But the first prompt design included `"Client: {client_id}"` as a line in the block the mock LLM echoes back, so `client_004`'s cached report literally displayed `"Client: client_001"` — a genuine correctness bug, not just a style issue. The fix: the prompt (and therefore anything cacheable) must never contain the client's identity at all. This is now a named regression test (`test_prompt_never_contains_a_client_identifier`, `test_two_clients_with_identical_findings_share_cache_without_leaking_identity`), not just a one-off fix.

Both bugs are the kind that are easy to miss if you only read code and trust it — they only became visible by actually running the thing end-to-end and inspecting real output, which is why that stayed the standard practice for this phase too (same as Phases 3 and 4).

## 3. Technology used and why

| Choice | Why | Alternative considered |
|---|---|---|
| Cache key excludes client identity, prompt excludes client identity | Lets genuinely different clients with the same findings pattern share a cache entry (real cost savings at any scale), safely — the cached text literally cannot say the wrong name because it never contains a name | Keying the cache by `(client_id, findings)` — simpler to reason about at first glance, but throws away the cross-client cache-sharing benefit for no real gain, since the client's identity belongs in the report metadata, not the narrative prose |
| Grounding via number-extraction + tolerance matching, not a second LLM call ("LLM judge") | Deterministic, free, instant — no extra API cost or latency to validate the first call's output | An LLM-as-judge step to verify groundedness — doubles the cost and latency for a check that a regex can do reliably for numeric claims specifically |
| `OpenAIClient` sets `max_retries=0` on the SDK client | So Phase 2's `with_retry` decorator (or a future one wrapping `generate()`) is the single place retry policy lives — two independent retry layers (SDK + ours) would double-retry and make timeout/backoff behavior unpredictable | Leaving the SDK's default retries on — "it just works" until you need to reason about exactly how many attempts happened and why |
| `MockLLMClient` echoes the prompt instead of generating independent fake prose | Makes the mock path *provably* grounded (it can only repeat numbers already in the prompt) rather than *coincidentally* grounded, which matters because this is the path every test and every no-API-key run actually exercises | A hand-written set of canned mock sentences — less maintenance-honest; could drift from the real findings and nobody would notice until a real LLM call revealed the drift |

## 4. Alternative approaches considered

- **Always call the LLM once per run, even with zero findings.** This is what I actually built — the alternative (skip the call entirely when `anomalies` is empty, to save even the token cost of a trivial call) was considered and rejected for predictability: "exactly one call per run" is a cleaner, more testable invariant than "zero or one, depending on data," and MockLLM/caching already make the zero-anomaly case free in practice anyway.
- **Validate the LLM's output with a Pydantic schema instead of a free-text grounding check.** `CLAUDE.md` generally prefers structured output over free-text parsing, and I considered having the LLM return `{"narrative": str, "numbers_used": list[float]}` so the numbers are explicit rather than regex-extracted. Rejected for this phase's scope: the narrative's job is prose for a human, and forcing a model to additionally self-report every number it used adds a failure mode (the self-report could itself be wrong or incomplete) without removing the need for grounding verification — the regex check still has to run either way, just against a smaller declared list. Worth revisiting if a future phase needs stronger guarantees.
- **Cache in-memory instead of SQLite.** Rejected — the whole point of "second identical run costs zero" is that it holds across separate CLI invocations (separate processes), which an in-memory cache can't do by definition. SQLite was already a locked decision in `planning.md` for exactly this kind of durable, zero-infrastructure state.

## 5. Expected interview questions

**Q: How does the grounding guard actually work — walk me through it on a real example.**
A: Before calling the LLM, the Analyzer's findings already contain every number that's allowed to appear ("$45,000.00", "94%", etc., each inside a finding's `explanation` string). After the LLM responds, `numeric_vocabulary()` builds the full list of legitimate numbers from those findings (plus the risk score and finding count), and `is_grounded()` scans the LLM's actual output text for anything that looks like a number and checks it against that list, with a small tolerance for rounding. If even one number in the output can't be matched to something real, the whole narrative is thrown away and replaced with the deterministic template — not edited, not partially trusted, fully replaced.
*Real-world example:* like a copy editor who doesn't fix a single wrong figure in a financial report — if one number in the draft can't be verified against the source data, the whole draft gets sent back and a pre-approved standard summary goes out instead, because a document with one wrong number next to five right ones is still not trustworthy.

**Q: Why can't the cache include the client's ID in the key?**
A: It *could* — but doing so throws away the main benefit of hashing by findings in the first place: two different clients who happen to have the same pattern of findings (say, both totally clean, or both hitting the exact same seeded anomaly set) would otherwise get two separate, identically-worded LLM calls for prose that would come out the same either way. The real fix needed wasn't to key by client — it was to make sure the cached text itself never contains anything client-specific, which is the only way to make cross-client cache sharing actually safe.
*Real-world example:* a form letter template ("Thank you for your order") can be reused for every customer precisely because it doesn't print one specific customer's name inside the reusable part — the personalization happens outside the template, in the greeting line added separately. If the template itself had someone's name baked in, reusing it for anyone else would be wrong by construction.

**Q: What would have happened if you'd shipped this without manually running the CLI, and only relied on unit tests you wrote from the spec?**
A: Very possibly both bugs would have shipped. A unit test for the grounding function, written abstractly, might have used clean test fixtures like `"client_test"` or `"test_1"` that happen not to trigger the regex bug, because I wasn't yet thinking about digit-in-identifier collisions until I saw the *actual* `fallback_reason: "ungrounded_output"` show up on a run that had every reason to succeed. Same with the cache bug — it only becomes visible when two *different* real client IDs happen to produce the *same* findings, which is an easy case to never think to write a test for until you literally see one client's report say another client's name.
*Real-world example:* this is the classic "works on my machine / works in my head" gap — a spec review catches logical errors, but only actually running the system catches the specific, concrete case where the clean abstraction meets messy real data.

**Q: Why does `OpenAIClient` set `max_retries=0`?**
A: Because retry policy needs to live in exactly one place to be reasoned about — if the SDK silently retries 2-3 times internally *and* a decorator around `generate()` also retries, you get multiplicative retry counts, unpredictable total latency, and no single place to look to answer "how many times did this actually try." Disabling the SDK's own retries makes `OpenAIClient` a pure adapter: one call in, one call out, and any retry/backoff policy is applied uniformly to every `LLMClient` implementation (mock included) at the call site, not buried inside one specific SDK's defaults.
*Real-world example:* like having exactly one person responsible for deciding whether to re-send a failed delivery, instead of both the courier and the warehouse independently deciding to resend — otherwise a customer might get three copies of the same package with nobody able to explain why.

**Q: What's the actual cost of running this system, and how do you know?**
A: Every run logs `llm_cost` — token counts and an estimated USD cost — whether the call hit the real OpenAI API, the cache, or fell back to the (free) template. With `MockLLMClient`, every run across every test and every no-key local run costs exactly `$0.00`, verified by `test_mock_llm_always_costs_zero`. With a real key, the system makes exactly one call per unique findings-pattern — a second identical run against the same client reuses the cache and costs `$0.00` too. The whole design is meant to make "what did this run cost" a line you can read off the JSON report, not something you have to estimate from a dashboard days later.

## 6. Scenario-based questions

**Q: "Someone sets `OPENAI_API_KEY` but it's invalid or the account has no credit." What happens?**
A: `OpenAIClient.generate()` raises (an authentication or rate-limit error from the SDK). `InsightAgent.run()` catches that exception, logs `llm_call_failed` with the error, and returns the deterministic template narrative with `llm_cost: {"tokens": 0, "estimated_cost_usd": 0.0, "fallback_reason": "llm_error"}`. The run still completes successfully — a bad API key degrades the narrative's richness, it doesn't break the system. This is the exact same philosophy as Phase 2's CRM fallback: the run always finishes, a failure just gets reported honestly in the output rather than crashing.
*Real-world example:* like a restaurant whose specialty dessert supplier didn't deliver today — the kitchen doesn't close, it serves the standard dessert menu instead and the waiter just doesn't push the specials.

**Q: "You need to A/B test two different prompt wordings to see which produces better narratives." How would you set that up given this architecture?**
A: Add a second prompt-builder function (or a `prompt_version` parameter to `build_insight_prompt`), make the cache key include the prompt version (so the two variants don't collide in the cache), and route some fraction of runs to each version — maybe via a config flag or a feature-flag service in a real deployment. Nothing about `LLMClient`, the grounding guard, or `InsightAgent`'s control flow would need to change — prompt content is already isolated in one file specifically so this kind of iteration doesn't ripple elsewhere.
*Real-world example:* like testing two versions of an email subject line through an email platform's A/B tool — the sending infrastructure and the tracking don't change, only the one piece of content being varied does.

**Q: "A compliance reviewer asks: 'could the LLM ever make up a client's account balance in its narrative?'" What's your answer, concretely?**
A: No — and here's the mechanism, not just an assurance: the LLM is never given account balances in the first place (the prompt only contains findings' `explanation` strings and the risk score, never raw account data), so it has nothing to hallucinate a *new* balance from. And even if it somehow produced a number through pure invention, `is_grounded()` would catch it the moment that number doesn't match anything in the real findings, and the response would be discarded in favor of the template. It's defense in depth: can't see the data it would need to fabricate convincingly, and even a fabricated number gets caught after the fact.
*Real-world example:* like a hospital giving a visiting specialist only the specific test results relevant to a consultation, not the patient's entire chart — even if they wanted to comment on something outside that scope, they simply don't have the information to do so convincingly.

**Q: "Running at scale, the SQLite cache file grows large and becomes a bottleneck." What would you change?**
A: `LLMCache`'s interface (`get`/`set`/`make_key`) is the only thing `InsightAgent` depends on — swapping the SQLite-backed implementation for a Redis-backed one (or Postgres, or any key-value store) with the same three methods wouldn't require touching `InsightAgent` at all. This is the same Strategy-pattern payoff as `LLMClient` itself: the agent depends on an interface, not a specific backend, so the backend is free to change as scale demands.
*Real-world example:* like a library switching its card catalog from paper index cards to a computer database — patrons still just ask "do you have this book," the lookup mechanism behind the desk is free to change without changing how anyone uses the library.
