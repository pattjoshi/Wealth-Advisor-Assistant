from __future__ import annotations

from typing import Any

# Bump this when the prompt's wording changes meaningfully — per CLAUDE.md, a prompt
# change should be followed by re-running the evals (Phase 9).
PROMPT_VERSION = "insight-v1"

SYSTEM_PROMPT = (
    "You are a wealth advisory assistant. Write a short, factual summary of the "
    "findings below for a human financial advisor reviewing this client. Use ONLY the "
    "numbers given below — never invent, estimate, or round a number that isn't "
    "already provided. Keep it under 120 words. This is not financial advice; only "
    "recommend reviewing findings with the client."
)

FINDINGS_MARKER = "FINDINGS SUMMARY:\n"
CLOSING_MARKER = "\n\nWrite the narrative now."


def build_insight_prompt(anomalies: list[dict[str, Any]], risk_score: float | None) -> str:
    """Builds a compact prompt from findings only — never raw transactions, full
    client records, or the client's identity. Two different clients with identical
    findings get an identical, cacheable prompt (E2 cost control: the cache is keyed
    by the findings, not the client, so this reuse is deliberate) — which also means
    the narrative text itself must never name a specific client, or a cache hit would
    leak one client's identity into another client's report."""
    lines = [f"Risk score: {risk_score}", f"Findings ({len(anomalies)}):"]
    if not anomalies:
        lines.append("- none")
    for finding in anomalies:
        lines.append(f"- [{finding['severity']}] {finding['type']}: {finding['explanation']}")
    findings_block = "\n".join(lines)
    return f"{SYSTEM_PROMPT}\n\n{FINDINGS_MARKER}{findings_block}{CLOSING_MARKER}"
