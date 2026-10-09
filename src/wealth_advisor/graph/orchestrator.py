from __future__ import annotations

from wealth_advisor.graph.state import WealthAdvisorState

MAX_STEPS = 12

STAGE_ORDER = ("data_fetcher", "analyzer", "insight")


def route(state: WealthAdvisorState) -> str:
    """Rule-based router — no LLM. Reads state, picks the next node, and always
    terminates: a hard step limit prevents any possibility of an infinite loop."""
    if state.get("step_count", 0) >= MAX_STEPS:
        return "finalize"

    if state.get("status") == "failed":
        return "finalize"  # data unusable -> go straight to the fail-safe report

    completed = {
        entry["agent"] for entry in state.get("trace", []) if entry.get("agent") in STAGE_ORDER
    }
    for stage in STAGE_ORDER:
        if stage not in completed:
            return stage

    return "finalize"
