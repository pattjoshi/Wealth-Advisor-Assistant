from pathlib import Path

from wealth_advisor.cli import build_app
from wealth_advisor.graph.state import new_state
from wealth_advisor.llm.mock_client import MockLLMClient

CLIENTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "clients"
CRM_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "crm" / "crm_records.json"


def _run(client_id: str, cache_db_path) -> dict:
    app = build_app(
        clients_dir=CLIENTS_DIR,
        crm_records_file=CRM_FILE,
        crm_failure_rate=0.0,
        llm_client=MockLLMClient(),
        cache_db_path=cache_db_path,
    )
    state = new_state(run_id="test-run", client_id=client_id, thread_id=client_id)
    return app.invoke(state)


def test_one_llm_call_per_run_not_per_anomaly(tmp_path) -> None:
    db_path = tmp_path / "cache.db"
    final = _run("client_002", db_path)  # client_002 has 4 anomalies

    insight_tool_calls = [
        e for e in final["trace"] if e.get("agent") == "insight" and e.get("tool") == "llm_client"
    ]
    assert len(insight_tool_calls) == 1


def test_cache_persists_across_separate_app_instances(tmp_path) -> None:
    """Simulates two separate CLI invocations sharing the same on-disk cache file."""
    db_path = tmp_path / "cache.db"

    first = _run("client_001", db_path)
    second = _run("client_001", db_path)

    assert first["llm_cost"]["cached"] is False
    assert second["llm_cost"]["cached"] is True
    assert second["llm_cost"]["estimated_cost_usd"] == 0.0


def test_different_findings_are_not_cache_confused(tmp_path) -> None:
    db_path = tmp_path / "cache.db"

    clean = _run("client_001", db_path)  # no anomalies
    anomalous = _run("client_002", db_path)  # 4 anomalies

    assert clean["insights"] != anomalous["insights"]


def test_two_clients_with_identical_findings_share_cache_without_leaking_identity(
    tmp_path,
) -> None:
    """Regression test for a real bug found during manual testing: client_001 and
    client_004 both have zero anomalies, so they hit the same cache entry — the
    narrative must stay generic and never show the other client's id."""
    db_path = tmp_path / "cache.db"

    first = _run("client_001", db_path)
    second = _run("client_004", db_path)

    assert first["llm_cost"]["cached"] is False
    assert second["llm_cost"]["cached"] is True
    assert "client_001" not in second["insights"]
    assert "client_004" not in second["insights"]
