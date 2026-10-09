from pathlib import Path

from wealth_advisor.cli import build_app
from wealth_advisor.graph.state import new_state

CLIENTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "clients"
CRM_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "crm" / "crm_records.json"


def _run(client_id: str, *, crm_failure_rate: float = 0.0) -> dict:
    app = build_app(
        clients_dir=CLIENTS_DIR, crm_records_file=CRM_FILE, crm_failure_rate=crm_failure_rate
    )
    state = new_state(run_id="test-run", client_id=client_id, thread_id=client_id)
    return app.invoke(state)


def test_happy_path_clean_client() -> None:
    final = _run("client_001")
    assert final["status"] == "completed"
    assert final["anomalies"] == []
    assert final["insights"] is not None
    assert final["errors"] == []


def test_happy_path_client_with_anomalies() -> None:
    final = _run("client_002")
    assert final["status"] == "completed"
    assert len(final["anomalies"]) == 4
    assert final["risk_score"] is not None
    assert "[MockLLM" in final["insights"]
    assert final["llm_cost"]["fallback_reason"] is None
    assert final["llm_cost"]["model"] == "mock-llm"


def test_crm_down_degrades_but_completes() -> None:
    final = _run("client_001", crm_failure_rate=1.0)
    assert final["status"] == "completed"
    assert "crm" in final["data_quality"]["degraded_sources"]
    # analysis still ran despite the degraded CRM
    assert final["metrics"] != {}


def test_client_not_found_is_a_clean_failure_not_a_crash() -> None:
    final = _run("client_999")
    assert final["status"] == "failed"
    assert final["anomalies"] == []
    assert any("client data unavailable" in e for e in final["errors"])


def test_malformed_client_is_a_clean_failure_not_a_crash() -> None:
    final = _run("client_005")
    assert final["status"] == "failed"
    assert any("transaction_id" in e for e in final["errors"])


def test_client_not_in_crm_still_completes() -> None:
    final = _run("client_004")
    assert final["status"] == "completed"
    assert "crm" in final["data_quality"]["degraded_sources"]
    assert any(
        "risk_profile_mismatch check skipped" in a for a in final["data_quality"]["assumptions"]
    )


def test_trace_records_every_agent_in_order() -> None:
    final = _run("client_001")
    agents_run = [entry["agent"] for entry in final["trace"] if entry.get("agent")]
    assert agents_run == ["data_fetcher", "data_fetcher", "analyzer", "analyzer", "insight"]


def test_step_count_increments_and_stays_bounded() -> None:
    final = _run("client_001")
    assert 1 <= final["step_count"] <= 10
