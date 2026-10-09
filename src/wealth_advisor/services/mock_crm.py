from __future__ import annotations

import json
import random
import time
from pathlib import Path


class CrmServiceError(Exception):
    pass


class MockCrmService:
    """In-process mock CRM with random latency and a configurable failure rate, so the
    tool layer's retry/fallback logic has something real to exercise. To swap in a real
    CRM, implement a class with the same get_profile(client_id) -> dict signature and
    pass it to CrmTool instead — nothing else in the system needs to change."""

    def __init__(
        self,
        records_path: Path,
        *,
        failure_rate: float = 0.0,
        min_latency_ms: float = 20.0,
        max_latency_ms: float = 150.0,
        rng: random.Random | None = None,
    ) -> None:
        self._records_path = records_path
        self._failure_rate = failure_rate
        self._min_latency_ms = min_latency_ms
        self._max_latency_ms = max_latency_ms
        self._rng = rng or random.Random()
        self._records: dict[str, dict] | None = None

    def _load_records(self) -> dict[str, dict]:
        if self._records is None:
            self._records = json.loads(self._records_path.read_text())
        return self._records

    def get_profile(self, client_id: str) -> dict:
        latency_s = self._rng.uniform(self._min_latency_ms, self._max_latency_ms) / 1000
        time.sleep(latency_s)

        if self._rng.random() < self._failure_rate:
            raise CrmServiceError(f"CRM request failed for '{client_id}' (simulated)")

        records = self._load_records()
        if client_id not in records:
            raise CrmServiceError(f"no CRM record for '{client_id}'")
        return records[client_id]
