from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from wealth_advisor.agents.analyzer import AnalyzerAgent
from wealth_advisor.agents.data_fetcher import DataFetcherAgent
from wealth_advisor.agents.insight import InsightAgent
from wealth_advisor.graph.orchestrator import decide
from wealth_advisor.graph.state import WealthAdvisorState
from wealth_advisor.observability.trace import log_routing_decision, wrap_node

_ROUTE_MAP = {
    "data_fetcher": "data_fetcher",
    "analyzer": "analyzer",
    "insight": "insight",
    "finalize": "finalize",
}


def build_graph(
    data_fetcher: DataFetcherAgent,
    analyzer: AnalyzerAgent,
    insight: InsightAgent,
) -> CompiledStateGraph:
    """Builder pattern: assembles the supervisor/hub-and-spoke StateGraph. Every agent
    node returns to the router (`_route_and_log`), which reads state and decides what
    runs next — the agents themselves never decide their own successor. Every node is
    wrapped for logging, timing, and a global exception safety net (see
    observability/trace.py)."""
    graph = StateGraph(WealthAdvisorState)

    graph.add_node("data_fetcher", wrap_node("data_fetcher", data_fetcher.run))
    graph.add_node("analyzer", wrap_node("analyzer", analyzer.run))
    graph.add_node("insight", wrap_node("insight", insight.run))
    graph.add_node("finalize", _finalize)

    graph.set_conditional_entry_point(_route_and_log, _ROUTE_MAP)
    for node_name in ("data_fetcher", "analyzer", "insight"):
        graph.add_conditional_edges(node_name, _route_and_log, _ROUTE_MAP)
    graph.add_edge("finalize", END)

    return graph.compile()


def _route_and_log(state: WealthAdvisorState) -> str:
    next_node, reason = decide(state)
    log_routing_decision(state, next_node, reason)
    return next_node


def _finalize(state: WealthAdvisorState) -> dict[str, Any]:
    status = "failed" if state.get("status") == "failed" else "completed"
    return {"status": status, "step_count": state.get("step_count", 0) + 1}
