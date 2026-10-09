from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from wealth_advisor.graph.state import WealthAdvisorState
from wealth_advisor.observability.logging import get_logger

log = get_logger()


def wrap_node(
    node_name: str, fn: Callable[[WealthAdvisorState], dict[str, Any]]
) -> Callable[[WealthAdvisorState], dict[str, Any]]:
    """Wraps a graph node with structured start/complete/failed logging, per-node
    timing, and step counting. Also the global exception handler: a node can never
    crash the run — any unexpected error here becomes a state error and the run still
    ends cleanly through the normal fail-safe route, instead of a raw traceback
    reaching the caller."""

    def node(state: WealthAdvisorState) -> dict[str, Any]:
        run_id = state.get("run_id", "unknown")
        bound_log = log.bind(run_id=run_id, node=node_name)
        start = time.monotonic()
        bound_log.info("node_started")

        try:
            update = fn(state)
        except Exception as exc:  # last-resort safety net; nodes must never crash the run
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            bound_log.error("node_failed", duration_ms=duration_ms, error=str(exc))
            errors = list(state.get("errors", []))
            errors.append(f"{node_name}: unexpected error: {exc}")
            return {
                "errors": errors,
                "status": "failed",
                "step_count": state.get("step_count", 0) + 1,
            }

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        bound_log.info("node_completed", duration_ms=duration_ms)
        update["step_count"] = state.get("step_count", 0) + 1
        return update

    return node


def log_routing_decision(state: WealthAdvisorState, next_node: str, reason: str) -> None:
    log.bind(run_id=state.get("run_id", "unknown")).info(
        "routing_decision",
        next_node=next_node,
        reason=reason,
        step_count=state.get("step_count", 0),
    )


def log_tool_call(state: WealthAdvisorState, entry: dict[str, Any]) -> None:
    log.bind(run_id=state.get("run_id", "unknown")).info("tool_call", **entry)
