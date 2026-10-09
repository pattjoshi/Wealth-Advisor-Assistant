from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from wealth_advisor.graph.state import WealthAdvisorState
from wealth_advisor.tools.base import ToolResult


class BaseAgent(ABC):
    """An agent receives its tools through its constructor (dependency injection) and
    never imports services/ directly. run() must return a partial state update and
    never mutate the `state` it was given."""

    name: str = "base_agent"

    @abstractmethod
    def run(self, state: WealthAdvisorState) -> dict[str, Any]:
        """Return a partial state update."""


def trace_entry(agent: str, tool: str | None, result: ToolResult[Any]) -> dict[str, Any]:
    return {
        "agent": agent,
        "tool": tool,
        "ok": result.ok,
        "source": result.source,
        "latency_ms": round(result.latency_ms, 2),
        "error": result.error,
    }
