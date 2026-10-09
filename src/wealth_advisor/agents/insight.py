from __future__ import annotations

from typing import Any

from wealth_advisor.agents.base import BaseAgent
from wealth_advisor.graph.state import WealthAdvisorState
from wealth_advisor.llm.base import LLMClient
from wealth_advisor.llm.cache import LLMCache
from wealth_advisor.llm.cost import estimate_cost_usd
from wealth_advisor.llm.grounding import is_grounded, numeric_vocabulary
from wealth_advisor.llm.prompts import build_insight_prompt
from wealth_advisor.observability.logging import get_logger

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}

log = get_logger()


class InsightAgent(BaseAgent):
    """Turns findings into a narrative via one LLM call per run (OpenAI, or MockLLM
    automatically when no API key is set — see llm/mock_client.py). A grounding guard
    rejects any output that mentions a number not present in the findings, falling
    back to a deterministic template instead: a wealth product can't risk an invented
    figure, so a failed guard is a degraded report, never a silently wrong one."""

    name = "insight"

    def __init__(self, llm_client: LLMClient, cache: LLMCache) -> None:
        self._llm_client = llm_client
        self._cache = cache

    def run(self, state: WealthAdvisorState) -> dict[str, Any]:
        trace = list(state.get("trace", []))
        anomalies = state.get("anomalies", [])
        risk_score = state.get("risk_score")
        client_id = state.get("client_id", "unknown")
        bound_log = log.bind(run_id=state.get("run_id", "unknown"))

        cache_key = LLMCache.make_key(
            self._llm_client.model, {"anomalies": anomalies, "risk_score": risk_score}
        )
        cached_response = self._cache.get(cache_key)
        cached = cached_response is not None

        if cached_response is not None:
            response = cached_response
        else:
            prompt = build_insight_prompt(anomalies, risk_score)
            try:
                response = self._llm_client.generate(prompt)
            except Exception as exc:
                bound_log.error("llm_call_failed", error=str(exc))
                return self._finalize(
                    state,
                    trace,
                    narrative=render_template_narrative(client_id, anomalies, risk_score),
                    tokens=0,
                    cost_usd=0.0,
                    cached=False,
                    model=self._llm_client.model,
                    fallback_reason="llm_error",
                    ok=False,
                    error=str(exc),
                )
            self._cache.set(cache_key, response)

        vocabulary = numeric_vocabulary(anomalies, risk_score)
        if is_grounded(response.text, vocabulary):
            narrative = response.text
            fallback_reason = None
        else:
            bound_log.error("llm_ungrounded_output", text=response.text)
            narrative = render_template_narrative(client_id, anomalies, risk_score)
            fallback_reason = "ungrounded_output"

        total_tokens = response.input_tokens + response.output_tokens
        cost_usd = (
            0.0
            if cached
            else estimate_cost_usd(response.model, response.input_tokens, response.output_tokens)
        )

        return self._finalize(
            state,
            trace,
            narrative=narrative,
            tokens=total_tokens,
            cost_usd=cost_usd,
            cached=cached,
            model=response.model,
            fallback_reason=fallback_reason,
            ok=fallback_reason is None,
            error=fallback_reason,
        )

    def _finalize(
        self,
        state: WealthAdvisorState,
        trace: list[dict[str, Any]],
        *,
        narrative: str,
        tokens: int,
        cost_usd: float,
        cached: bool,
        model: str,
        fallback_reason: str | None,
        ok: bool,
        error: str | None,
    ) -> dict[str, Any]:
        llm_cost = {
            "tokens": tokens,
            "estimated_cost_usd": cost_usd,
            "cached": cached,
            "model": model,
            "fallback_reason": fallback_reason,
        }
        log.bind(run_id=state.get("run_id", "unknown")).info("llm_cost", **llm_cost)
        trace.append(
            {
                "agent": self.name,
                "tool": "llm_client",
                "ok": ok,
                "source": "cache" if cached else model,
                "latency_ms": 0.0,
                "error": error,
            }
        )
        return {"insights": narrative, "llm_cost": llm_cost, "trace": trace}


def render_template_narrative(
    client_id: str, anomalies: list[dict[str, Any]], risk_score: float | None
) -> str:
    """The deterministic fallback used when the LLM call fails or its output isn't
    grounded in the real findings. Also what a MockLLM-free, LLM-free run would look
    like — kept from Phase 3 unchanged."""
    if not anomalies:
        return (
            f"No notable anomalies were detected for {client_id} in this review. "
            "Portfolio and transaction activity appear consistent with the client's "
            "normal pattern."
        )

    high_count = sum(1 for a in anomalies if a["severity"] == "high")
    lines = [f"{len(anomalies)} finding(s) identified for {client_id} (risk score {risk_score}):"]
    for finding in sorted(anomalies, key=lambda a: SEVERITY_ORDER[a["severity"]], reverse=True):
        lines.append(f"- [{finding['severity'].upper()}] {finding['explanation']}")
    if high_count:
        lines.append(
            "Recommended action: review the high-severity item(s) with the client "
            "before the next scheduled contact."
        )
    return "\n".join(lines)
