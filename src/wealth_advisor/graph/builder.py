from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from wealth_advisor.agents.analyzer import AnalyzerAgent
from wealth_advisor.agents.data_fetcher import DataFetcherAgent
from wealth_advisor.agents.insight import InsightAgent
from wealth_advisor.graph.orchestrator import route
from wealth_advisor.graph.state import WealthAdvisorState

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
    node returns to the router (`route`), which reads state and decides what runs
    next — the agents themselves never decide their own successor."""
    graph = StateGraph(WealthAdvisorState)

    graph.add_node("data_fetcher", _count_step(data_fetcher.run))
    graph.add_node("analyzer", _count_step(analyzer.run))
    graph.add_node("insight", _count_step(insight.run))
    graph.add_node("finalize", _finalize)

    graph.set_conditional_entry_point(route, _ROUTE_MAP)
    for node_name in ("data_fetcher", "analyzer", "insight"):
        graph.add_conditional_edges(node_name, route, _ROUTE_MAP)
    graph.add_edge("finalize", END)

    return graph.compile()


def _count_step(
    fn: Callable[[WealthAdvisorState], dict[str, Any]],
) -> Callable[[WealthAdvisorState], dict[str, Any]]:
    def node(state: WealthAdvisorState) -> dict[str, Any]:
        update = fn(state)
        update["step_count"] = state.get("step_count", 0) + 1
        return update

    return node


def _finalize(state: WealthAdvisorState) -> dict[str, Any]:
    status = "failed" if state.get("status") == "failed" else "completed"
    return {"status": status, "step_count": state.get("step_count", 0) + 1}
