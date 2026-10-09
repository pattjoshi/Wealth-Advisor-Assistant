from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from wealth_advisor.graph.state import AnomalyFinding, DataQualityReport, LLMCostReport


class AdvisoryReport(BaseModel):
    """The structured JSON output of a run (R10). This is what the CLI prints and
    what a Streamlit UI (Phase 8) or a downstream system would consume."""

    run_id: str
    client_id: str
    status: Literal["completed", "failed"]
    risk_score: float | None
    anomalies: list[AnomalyFinding]
    metrics: dict[str, Any]
    insights: str | None
    llm_cost: LLMCostReport | None
    data_quality: DataQualityReport
    errors: list[str]
