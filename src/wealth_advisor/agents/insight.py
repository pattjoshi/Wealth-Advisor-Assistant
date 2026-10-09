from __future__ import annotations

from typing import Any

from wealth_advisor.agents.base import BaseAgent
from wealth_advisor.graph.state import WealthAdvisorState

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


class InsightAgent(BaseAgent):
    """Turns findings into a plain-English narrative. Phase 3 is template-only (no
    LLM) — Phase 5 adds an LLM client behind the same interface for the narrative
    text, with the numbers still coming from the Analyzer either way."""

    name = "insight"

    def run(self, state: WealthAdvisorState) -> dict[str, Any]:
        trace = list(state.get("trace", []))
        anomalies = state.get("anomalies", [])
        risk_score = state.get("risk_score")
        client_id = state.get("client_id", "unknown")

        narrative = _render_narrative(client_id, anomalies, risk_score)

        trace.append(
            {
                "agent": self.name,
                "tool": None,
                "ok": True,
                "source": "template",
                "latency_ms": 0.0,
                "error": None,
            }
        )
        return {"insights": narrative, "trace": trace}


def _render_narrative(
    client_id: str, anomalies: list[dict[str, Any]], risk_score: float | None
) -> str:
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
