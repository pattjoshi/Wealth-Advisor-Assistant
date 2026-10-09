from __future__ import annotations

from typing import Any

from wealth_advisor.agents.base import BaseAgent, trace_entry
from wealth_advisor.graph.state import WealthAdvisorState
from wealth_advisor.observability.trace import log_tool_call
from wealth_advisor.tools.client_data import ClientDataTool
from wealth_advisor.tools.crm import CrmTool


class DataFetcherAgent(BaseAgent):
    """Loads a client's financial data and CRM profile, and records what's missing or
    degraded so later agents — and the final report — can be honest about data
    quality instead of pretending everything was available."""

    name = "data_fetcher"

    def __init__(self, client_data_tool: ClientDataTool, crm_tool: CrmTool) -> None:
        self._client_data_tool = client_data_tool
        self._crm_tool = crm_tool

    def run(self, state: WealthAdvisorState) -> dict[str, Any]:
        client_id = state["client_id"]
        errors = list(state.get("errors", []))
        trace = list(state.get("trace", []))
        missing_fields: list[str] = []
        assumptions: list[str] = []
        degraded_sources: list[str] = []

        client_result = self._client_data_tool.execute(client_id=client_id)
        client_entry = trace_entry(self.name, "client_data_tool", client_result)
        trace.append(client_entry)
        log_tool_call(state, client_entry)

        client_data: dict[str, Any] | None = None
        status = "running"
        if client_result.ok:
            profile = client_result.data
            client_data = profile.model_dump(mode="json")
            if profile.date_of_birth is None:
                missing_fields.append("date_of_birth")
            if not profile.transactions:
                assumptions.append(
                    "no transactions on file; transaction-based anomaly checks were skipped"
                )
        else:
            errors.append(f"{self.name}: client data unavailable: {client_result.error}")
            status = "failed"

        crm_result = self._crm_tool.execute(client_id=client_id)
        crm_entry = trace_entry(self.name, "crm_tool", crm_result)
        trace.append(crm_entry)
        log_tool_call(state, crm_entry)

        crm_profile: dict[str, Any] | None = None
        if crm_result.ok:
            crm_data = crm_result.data
            crm_profile = crm_data.model_dump(mode="json")
            if crm_data.status == "degraded":
                degraded_sources.append("crm")
                assumptions.append(
                    "CRM profile unavailable; used a default profile and the "
                    "risk-profile-mismatch check will be skipped"
                )
        else:
            errors.append(f"{self.name}: CRM lookup failed: {crm_result.error}")
            degraded_sources.append("crm")

        return {
            "client_data": client_data,
            "crm_profile": crm_profile,
            "data_quality": {
                "missing_fields": missing_fields,
                "assumptions": assumptions,
                "degraded_sources": degraded_sources,
            },
            "errors": errors,
            "trace": trace,
            "status": status,
        }
