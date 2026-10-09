from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from langgraph.graph.state import CompiledStateGraph

from wealth_advisor.agents.analyzer import AnalyzerAgent
from wealth_advisor.agents.data_fetcher import DataFetcherAgent
from wealth_advisor.agents.insight import InsightAgent
from wealth_advisor.config import settings
from wealth_advisor.graph.builder import build_graph
from wealth_advisor.graph.state import new_state
from wealth_advisor.observability.logging import configure_logging
from wealth_advisor.schemas.report import AdvisoryReport
from wealth_advisor.services.mock_crm import MockCrmService
from wealth_advisor.tools.anomaly_detection import AnomalyDetectionTool
from wealth_advisor.tools.client_data import ClientDataTool
from wealth_advisor.tools.crm import CrmTool
from wealth_advisor.tools.portfolio_metrics import PortfolioMetricsTool


def build_app(
    *, clients_dir: Path, crm_records_file: Path, crm_failure_rate: float
) -> CompiledStateGraph:
    client_data_tool = ClientDataTool(clients_dir)
    crm_service = MockCrmService(crm_records_file, failure_rate=crm_failure_rate)
    crm_tool = CrmTool(crm_service)
    data_fetcher = DataFetcherAgent(client_data_tool, crm_tool)

    analyzer = AnalyzerAgent(PortfolioMetricsTool(), AnomalyDetectionTool())
    insight = InsightAgent()

    return build_graph(data_fetcher, analyzer, insight)


def run_client(client_id: str, *, crm_failure_rate: float | None = None) -> AdvisoryReport:
    app = build_app(
        clients_dir=settings.clients_dir,
        crm_records_file=settings.resolved_crm_records_file,
        crm_failure_rate=(
            crm_failure_rate if crm_failure_rate is not None else settings.crm_failure_rate
        ),
    )
    run_id = str(uuid.uuid4())
    initial_state = new_state(run_id=run_id, client_id=client_id, thread_id=client_id)
    final_state = app.invoke(initial_state)

    return AdvisoryReport(
        run_id=final_state["run_id"],
        client_id=final_state["client_id"],
        status=final_state.get("status", "failed"),
        risk_score=final_state.get("risk_score"),
        anomalies=final_state.get("anomalies", []),
        metrics=final_state.get("metrics", {}),
        insights=final_state.get("insights"),
        data_quality=final_state.get(
            "data_quality", {"missing_fields": [], "assumptions": [], "degraded_sources": []}
        ),
        errors=final_state.get("errors", []),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wealth-advisor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the advisory pipeline for one client")
    run_parser.add_argument("--client", required=True, help="Client ID, e.g. client_001")
    run_parser.add_argument(
        "--simulate-crm-failure",
        action="store_true",
        help="Force every CRM call to fail this run, to demonstrate the fallback path",
    )

    args = parser.parse_args(argv)

    if args.command == "run":
        configure_logging(log_level=settings.log_level, log_file=settings.log_file)
        crm_failure_rate = 1.0 if args.simulate_crm_failure else None
        report = run_client(args.client, crm_failure_rate=crm_failure_rate)
        sys.stdout.write(report.model_dump_json(indent=2) + "\n")
        return 0 if report.status == "completed" else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
