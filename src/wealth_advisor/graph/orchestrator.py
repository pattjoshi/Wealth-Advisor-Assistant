from __future__ import annotations

from wealth_advisor.graph.state import WealthAdvisorState

MAX_STEPS = 12

STAGE_ORDER = ("data_fetcher", "analyzer", "insight")


def decide(state: WealthAdvisorState) -> tuple[str, str]:
    """Rule-based router — no LLM. Reads state, picks the next node, and returns the
    reason too, so callers that log (graph/builder.py) can record *why* a decision was
    made, not just what it was."""
    if state.get("step_count", 0) >= MAX_STEPS:
        return "finalize", f"max step limit ({MAX_STEPS}) reached"

    if state.get("status") == "failed":
        return "finalize", "data unusable; routing straight to the fail-safe report"

    completed = {
        entry["agent"] for entry in state.get("trace", []) if entry.get("agent") in STAGE_ORDER
    }
    for stage in STAGE_ORDER:
        if stage not in completed:
            return stage, f"'{stage}' has not run yet"

    return "finalize", "all stages completed"


def route(state: WealthAdvisorState) -> str:
    """Thin wrapper over decide() for callers that only need the next node name."""
    return decide(state)[0]
