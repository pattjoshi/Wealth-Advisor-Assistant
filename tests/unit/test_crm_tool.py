import json
from pathlib import Path

import pytest

from wealth_advisor.services.mock_crm import CrmServiceError, MockCrmService
from wealth_advisor.tools.crm import CrmTool

CRM_RECORD = {
    "client_id": "client_001",
    "risk_tolerance": "moderate",
    "goals": ["retirement"],
}


@pytest.fixture
def records_path(tmp_path: Path) -> Path:
    path = tmp_path / "crm_records.json"
    path.write_text(json.dumps({"client_001": CRM_RECORD}))
    return path


class _ScriptedCrmService(MockCrmService):
    """A service whose get_profile() follows a scripted sequence of outcomes, to test
    retry and fallback behavior deterministically instead of relying on randomness."""

    def __init__(self, records_path: Path, outcomes: list[Exception | None]) -> None:
        super().__init__(records_path, failure_rate=0.0, min_latency_ms=0, max_latency_ms=0)
        self._outcomes = list(outcomes)

    def get_profile(self, client_id: str) -> dict:
        outcome = self._outcomes.pop(0) if self._outcomes else None
        if outcome is not None:
            raise outcome
        return super().get_profile(client_id)


def test_success_on_first_attempt(records_path: Path) -> None:
    service = _ScriptedCrmService(records_path, outcomes=[None])
    tool = CrmTool(service)

    result = tool.execute(client_id="client_001")

    assert result.ok is True
    assert result.data.status == "ok"
    assert result.data.client_id == "client_001"


def test_retry_then_success(records_path: Path) -> None:
    service = _ScriptedCrmService(
        records_path,
        outcomes=[CrmServiceError("down"), CrmServiceError("down"), None],
    )
    tool = CrmTool(service, max_retry_attempts=3)

    result = tool.execute(client_id="client_001")

    assert result.ok is True
    assert result.data.status == "ok"


def test_total_failure_falls_back_to_default_degraded_profile(records_path: Path) -> None:
    service = _ScriptedCrmService(records_path, outcomes=[CrmServiceError("down")] * 10)
    tool = CrmTool(service, max_retry_attempts=2)

    result = tool.execute(client_id="client_999")

    assert result.ok is True  # the tool call itself never fails
    assert result.data.status == "degraded"
    assert result.data.client_id == "client_999"


def test_total_failure_falls_back_to_cache_before_default(records_path: Path) -> None:
    service = _ScriptedCrmService(records_path, outcomes=[None])
    tool = CrmTool(service, max_retry_attempts=1)

    first = tool.execute(client_id="client_001")
    assert first.ok is True
    assert first.data.status == "ok"

    service._outcomes = [CrmServiceError("down")] * 10
    second = tool.execute(client_id="client_001")

    assert second.ok is True
    assert second.data.status == "ok"  # served from cache, not degraded
    assert second.data is first.data
