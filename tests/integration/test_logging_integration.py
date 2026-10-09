import json

from wealth_advisor import cli as cli_module
from wealth_advisor.config import settings


def test_cli_stdout_is_only_the_report_and_log_file_is_structured(
    tmp_path, monkeypatch, capsys
) -> None:
    log_file = tmp_path / "run.jsonl"
    monkeypatch.setattr(settings, "log_file", log_file)

    exit_code = cli_module.main(["run", "--client", "client_001"])

    assert exit_code == 0

    captured = capsys.readouterr()
    report = json.loads(captured.out)  # stdout must be ONLY the report JSON, nothing else
    assert report["client_id"] == "client_001"
    assert report["status"] == "completed"

    assert log_file.exists()
    lines = [line for line in log_file.read_text().strip().splitlines() if line]
    assert len(lines) > 0

    entries = [json.loads(line) for line in lines]
    for entry in entries:
        assert entry["run_id"] == report["run_id"]

    events = {entry["event"] for entry in entries}
    assert "routing_decision" in events
    assert "node_started" in events
    assert "node_completed" in events
    assert "tool_call" in events


def test_cli_log_file_marks_crm_failure_run_as_degraded(tmp_path, monkeypatch, capsys) -> None:
    log_file = tmp_path / "run.jsonl"
    monkeypatch.setattr(settings, "log_file", log_file)

    exit_code = cli_module.main(["run", "--client", "client_001", "--simulate-crm-failure"])

    assert exit_code == 0
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["status"] == "completed"
    assert "crm" in report["data_quality"]["degraded_sources"]

    entries = [json.loads(line) for line in log_file.read_text().strip().splitlines() if line]
    tool_calls = [e for e in entries if e["event"] == "tool_call" and e["tool"] == "crm_tool"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["ok"] is True  # CrmTool never fails the call itself, just degrades


def test_cli_malformed_client_still_produces_readable_logs(tmp_path, monkeypatch, capsys) -> None:
    log_file = tmp_path / "run.jsonl"
    monkeypatch.setattr(settings, "log_file", log_file)

    exit_code = cli_module.main(["run", "--client", "client_005"])

    assert exit_code == 1
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["status"] == "failed"

    entries = [json.loads(line) for line in log_file.read_text().strip().splitlines() if line]
    assert any(e["event"] == "node_completed" and e["node"] == "data_fetcher" for e in entries)
