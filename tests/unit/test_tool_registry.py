from typing import Any

import pytest

from wealth_advisor.tools.base import BaseTool
from wealth_advisor.tools.registry import ToolRegistry


class _DummyTool(BaseTool[str]):
    name = "dummy_tool"

    def _run(self, **_: Any) -> str:
        return "ok"


def test_register_and_get() -> None:
    registry = ToolRegistry()
    tool = _DummyTool()
    registry.register(tool)

    assert "dummy_tool" in registry
    assert registry.get("dummy_tool") is tool
    assert registry.names() == ["dummy_tool"]


def test_duplicate_registration_raises() -> None:
    registry = ToolRegistry()
    registry.register(_DummyTool())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_DummyTool())


def test_unknown_tool_raises_clear_error() -> None:
    registry = ToolRegistry()
    with pytest.raises(KeyError, match="no tool registered"):
        registry.get("missing_tool")
