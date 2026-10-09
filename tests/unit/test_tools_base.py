from typing import Any

from wealth_advisor.tools.base import BaseTool, ToolResult


class _EchoTool(BaseTool[str]):
    name = "echo_tool"

    def validate(self, **kwargs: Any) -> None:
        if "value" not in kwargs:
            raise ValueError("value is required")

    def _run(self, *, value: str, **_: Any) -> str:
        return value


class _ExplodingTool(BaseTool[str]):
    name = "exploding_tool"

    def _run(self, **_: Any) -> str:
        raise RuntimeError("boom")


def test_successful_execution_wraps_result() -> None:
    result = _EchoTool().execute(value="hello")
    assert result.ok is True
    assert result.data == "hello"
    assert result.error is None
    assert result.source == "echo_tool"
    assert result.latency_ms >= 0


def test_validation_failure_never_raises() -> None:
    result = _EchoTool().execute()
    assert result.ok is False
    assert result.data is None
    assert "value is required" in result.error


def test_run_exception_never_raises() -> None:
    result = _ExplodingTool().execute()
    assert result.ok is False
    assert "boom" in result.error


def test_tool_result_factories() -> None:
    ok = ToolResult.success("data", source="t", latency_ms=1.0)
    assert ok.ok is True

    bad = ToolResult.failure("oops", source="t", latency_ms=1.0)
    assert bad.ok is False
    assert bad.error == "oops"
