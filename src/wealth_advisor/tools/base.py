from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ToolResult(Generic[T]):
    ok: bool
    data: T | None
    error: str | None
    source: str
    latency_ms: float

    @classmethod
    def success(cls, data: T, *, source: str, latency_ms: float) -> ToolResult[T]:
        return cls(ok=True, data=data, error=None, source=source, latency_ms=latency_ms)

    @classmethod
    def failure(cls, error: str, *, source: str, latency_ms: float) -> ToolResult[T]:
        return cls(ok=False, data=None, error=error, source=source, latency_ms=latency_ms)


class BaseTool(ABC, Generic[T]):
    """Template Method: execute() always validates, runs, times, and converts any
    exception into a failed ToolResult. Subclasses only implement validate()/_run() and
    never need to think about error handling themselves — agents calling execute() never
    see a raised exception."""

    name: str = "base_tool"

    def execute(self, **kwargs: Any) -> ToolResult[T]:
        start = time.monotonic()
        try:
            self.validate(**kwargs)
            data = self._run(**kwargs)
        except Exception as exc:  # tools must never raise to the caller
            latency_ms = (time.monotonic() - start) * 1000
            return ToolResult.failure(str(exc), source=self.name, latency_ms=latency_ms)
        latency_ms = (time.monotonic() - start) * 1000
        return ToolResult.success(data, source=self.name, latency_ms=latency_ms)

    def validate(self, **kwargs: Any) -> None:
        """Override to raise on bad arguments before _run() executes. No-op by default."""

    @abstractmethod
    def _run(self, **kwargs: Any) -> T:
        """Do the tool's work. May raise freely — execute() catches and wraps it."""
