import json
import random
from pathlib import Path

import pytest

from wealth_advisor.services.mock_crm import CrmServiceError, MockCrmService


@pytest.fixture
def records_path(tmp_path: Path) -> Path:
    path = tmp_path / "crm_records.json"
    record = {"client_id": "client_001", "risk_tolerance": "moderate"}
    path.write_text(json.dumps({"client_001": record}))
    return path


def test_known_client_succeeds_with_zero_failure_rate(records_path: Path) -> None:
    service = MockCrmService(
        records_path, failure_rate=0.0, min_latency_ms=0, max_latency_ms=1, rng=random.Random(1)
    )
    profile = service.get_profile("client_001")
    assert profile["client_id"] == "client_001"


def test_unknown_client_raises(records_path: Path) -> None:
    service = MockCrmService(
        records_path, failure_rate=0.0, min_latency_ms=0, max_latency_ms=1, rng=random.Random(1)
    )
    with pytest.raises(CrmServiceError, match="no CRM record"):
        service.get_profile("client_999")


def test_always_fails_with_failure_rate_one(records_path: Path) -> None:
    service = MockCrmService(
        records_path, failure_rate=1.0, min_latency_ms=0, max_latency_ms=1, rng=random.Random(1)
    )
    with pytest.raises(CrmServiceError, match="simulated"):
        service.get_profile("client_001")
