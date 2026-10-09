from __future__ import annotations

from typing import Any, Literal, TypedDict

RunStatus = Literal["running", "needs_review", "completed", "failed"]


class AnomalyFinding(TypedDict):
    id: str
    type: str
    severity: Literal["low", "medium", "high"]
    evidence: dict[str, Any]
    explanation: str
    is_recurring: bool


class DataQualityReport(TypedDict):
    missing_fields: list[str]
    assumptions: list[str]
    degraded_sources: list[str]


class LLMCostReport(TypedDict):
    tokens: int
    estimated_cost_usd: float
    cached: bool
    model: str
    fallback_reason: str | None


class WealthAdvisorState(TypedDict, total=False):
    """Shared graph state. Nodes return partial updates (a dict with only the keys they
    changed); LangGraph merges them. Never mutate a state value returned from a node —
    always build and return a new value."""

    run_id: str
    client_id: str
    thread_id: str

    client_data: dict[str, Any] | None
    crm_profile: dict[str, Any] | None
    data_quality: DataQualityReport

    metrics: dict[str, Any]
    anomalies: list[AnomalyFinding]
    risk_score: float | None

    insights: str | None
    llm_cost: LLMCostReport | None

    review_decision: str | None

    errors: list[str]
    trace: list[dict[str, Any]]
    step_count: int
    status: RunStatus


def new_state(*, run_id: str, client_id: str, thread_id: str) -> WealthAdvisorState:
    return WealthAdvisorState(
        run_id=run_id,
        client_id=client_id,
        thread_id=thread_id,
        client_data=None,
        crm_profile=None,
        data_quality={"missing_fields": [], "assumptions": [], "degraded_sources": []},
        metrics={},
        anomalies=[],
        risk_score=None,
        insights=None,
        llm_cost=None,
        review_decision=None,
        errors=[],
        trace=[],
        step_count=0,
        status="running",
    )
