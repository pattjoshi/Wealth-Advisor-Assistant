from __future__ import annotations

import concurrent.futures
import functools
import time
from collections.abc import Callable
from typing import TypeVar

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

T = TypeVar("T")


class ToolTimeoutError(Exception):
    pass


class CircuitBreakerOpenError(Exception):
    pass


def with_retry(
    *,
    max_attempts: int = 3,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry with exponential backoff, only on the given exception types."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=0.05, min=0.05, max=1),
        retry=retry_if_exception_type(exceptions),
        reraise=True,
    )


def with_timeout(seconds: float) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Run a call on a worker thread and raise ToolTimeoutError if it doesn't finish in
    time. Works for any blocking call, sync code included (no asyncio required)."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: object, **kwargs: object) -> T:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=seconds)
                except concurrent.futures.TimeoutError as exc:
                    raise ToolTimeoutError(f"{func.__name__} timed out after {seconds}s") from exc

        return wrapper

    return decorator


class CircuitBreaker:
    """Simple closed/open/half-open circuit breaker. After `failure_threshold`
    consecutive failures it opens and rejects calls immediately (no wasted retries)
    until `reset_timeout` elapses, then allows one trial call (half-open)."""

    def __init__(self, *, failure_threshold: int = 3, reset_timeout: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failure_count = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        return time.monotonic() - self._opened_at < self.reset_timeout

    def call(self, func: Callable[[], T]) -> T:
        if self.is_open:
            raise CircuitBreakerOpenError("circuit breaker is open")
        try:
            result = func()
        except Exception:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._opened_at = time.monotonic()
            raise
        else:
            self._failure_count = 0
            self._opened_at = None
            return result
