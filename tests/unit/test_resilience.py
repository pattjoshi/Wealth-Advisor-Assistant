import time

import pytest

from wealth_advisor.tools.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    ToolTimeoutError,
    with_retry,
    with_timeout,
)


def test_retry_succeeds_after_transient_failures() -> None:
    attempts = {"count": 0}

    @with_retry(max_attempts=3, exceptions=(ValueError,))
    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ValueError("transient")
        return "ok"

    assert flaky() == "ok"
    assert attempts["count"] == 3


def test_retry_exhausts_and_reraises() -> None:
    @with_retry(max_attempts=2, exceptions=(ValueError,))
    def always_fails() -> str:
        raise ValueError("permanent")

    with pytest.raises(ValueError, match="permanent"):
        always_fails()


def test_retry_does_not_catch_other_exceptions() -> None:
    @with_retry(max_attempts=3, exceptions=(ValueError,))
    def wrong_error() -> str:
        raise RuntimeError("not retried")

    with pytest.raises(RuntimeError, match="not retried"):
        wrong_error()


def test_timeout_raises_on_slow_call() -> None:
    @with_timeout(0.05)
    def slow() -> str:
        time.sleep(0.5)
        return "too late"

    with pytest.raises(ToolTimeoutError):
        slow()


def test_timeout_passes_through_fast_call() -> None:
    @with_timeout(1.0)
    def fast() -> str:
        return "on time"

    assert fast() == "on time"


def test_circuit_breaker_opens_after_threshold() -> None:
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout=60.0)

    def failing() -> None:
        raise RuntimeError("down")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            breaker.call(failing)

    assert breaker.is_open is True
    with pytest.raises(CircuitBreakerOpenError):
        breaker.call(failing)


def test_circuit_breaker_resets_after_timeout() -> None:
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout=0.05)

    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("down")))

    assert breaker.is_open is True
    time.sleep(0.1)
    assert breaker.is_open is False

    assert breaker.call(lambda: "recovered") == "recovered"
