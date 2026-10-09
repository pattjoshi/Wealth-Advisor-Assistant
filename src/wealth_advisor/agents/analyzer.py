from __future__ import annotations

from typing import Any

from wealth_advisor.agents.base import BaseAgent, trace_entry
from wealth_advisor.graph.state import WealthAdvisorState
from wealth_advisor.schemas.client import ClientProfile
from wealth_advisor.schemas.crm import CrmProfile
from wealth_advisor.tools.anomaly_detection import AnomalyDetectionTool
from wealth_advisor.tools.portfolio_metrics import PortfolioMetricsTool


class AnalyzerAgent(BaseAgent):
    """Computes portfolio metrics and runs the ten deterministic anomaly/risk checks.
    No LLM here — every number and every finding is reproducible Python."""

    name = "analyzer"

    def __init__(
        self,
        portfolio_metrics_tool: PortfolioMetricsTool,
        anomaly_detection_tool: AnomalyDetectionTool,
    ) -> None:
        self._portfolio_metrics_tool = portfolio_metrics_tool
        self._anomaly_detection_tool = anomaly_detection_tool

    def run(self, state: WealthAdvisorState) -> dict[str, Any]:
        trace = list(state.get("trace", []))
        errors = list(state.get("errors", []))
        data_quality = dict(
            state.get(
                "data_quality",
                {"missing_fields": [], "assumptions": [], "degraded_sources": []},
            )
        )
        assumptions = list(data_quality.get("assumptions", []))

        client_data = state.get("client_data")
        if not client_data:
            errors.append(f"{self.name}: no client data available; skipping analysis")
            return {
                "metrics": {},
                "anomalies": [],
                "risk_score": None,
                "errors": errors,
                "trace": trace,
            }

        client = ClientProfile.model_validate(client_data)
        crm_data = state.get("crm_profile")
        crm_profile = CrmProfile.model_validate(crm_data) if crm_data else None

        metrics_result = self._portfolio_metrics_tool.execute(client=client)
        trace.append(trace_entry(self.name, "portfolio_metrics_tool", metrics_result))
        metrics: dict[str, Any] = metrics_result.data if metrics_result.ok else {}
        if not metrics_result.ok:
            errors.append(f"{self.name}: portfolio metrics failed: {metrics_result.error}")

        anomaly_result = self._anomaly_detection_tool.execute(
            client=client, metrics=metrics, crm_profile=crm_profile
        )
        trace.append(trace_entry(self.name, "anomaly_detection_tool", anomaly_result))

        if not anomaly_result.ok:
            errors.append(f"{self.name}: anomaly detection failed: {anomaly_result.error}")
            return {
                "metrics": metrics,
                "anomalies": [],
                "risk_score": None,
                "data_quality": {**data_quality, "assumptions": assumptions},
                "errors": errors,
                "trace": trace,
            }

        result_data = anomaly_result.data
        assumptions.extend(result_data["assumptions"])

        return {
            "metrics": metrics,
            "anomalies": result_data["findings"],
            "risk_score": result_data["risk_score"],
            "data_quality": {**data_quality, "assumptions": assumptions},
            "errors": errors,
            "trace": trace,
        }
