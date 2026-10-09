from __future__ import annotations

from typing import Any

from wealth_advisor.schemas.crm import CrmProfile
from wealth_advisor.services.mock_crm import CrmServiceError, MockCrmService
from wealth_advisor.tools.base import BaseTool
from wealth_advisor.tools.resilience import CircuitBreaker, CircuitBreakerOpenError, with_retry


class CrmTool(BaseTool[CrmProfile]):
    """Fallback order: live call (retried) -> last cached profile for this client ->
    a default profile marked status="degraded". The tool always returns ok=True for a
    known client_id — a down CRM degrades the data, it never fails the tool call."""

    name = "crm_tool"

    def __init__(
        self,
        service: MockCrmService,
        *,
        max_retry_attempts: int = 3,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._service = service
        self._max_retry_attempts = max_retry_attempts
        self._circuit_breaker = circuit_breaker or CircuitBreaker()
        self._cache: dict[str, CrmProfile] = {}

    def validate(self, **kwargs: Any) -> None:
        if not kwargs.get("client_id"):
            raise ValueError("client_id is required")

    def _run(self, *, client_id: str, **_: Any) -> CrmProfile:
        try:
            profile = self._circuit_breaker.call(lambda: self._fetch_with_retry(client_id))
        except (CrmServiceError, CircuitBreakerOpenError):
            return self._fallback(client_id)
        self._cache[client_id] = profile
        return profile

    def _fetch_with_retry(self, client_id: str) -> CrmProfile:
        fetch = with_retry(max_attempts=self._max_retry_attempts, exceptions=(CrmServiceError,))(
            self._service.get_profile
        )
        raw = fetch(client_id)
        return CrmProfile.model_validate(raw)

    def _fallback(self, client_id: str) -> CrmProfile:
        if client_id in self._cache:
            return self._cache[client_id]
        return CrmProfile(
            client_id=client_id,
            risk_tolerance="moderate",
            goals=[],
            last_contact=None,
            advisor_notes="CRM unavailable and no cached profile; using defaults.",
            status="degraded",
        )
