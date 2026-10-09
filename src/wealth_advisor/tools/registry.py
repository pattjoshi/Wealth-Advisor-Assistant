from __future__ import annotations

from wealth_advisor.tools.base import BaseTool


class ToolRegistry:
    """Discoverable collection of tools, keyed by name. Agents receive a registry (or
    the specific tools they need) through dependency injection — never import a tool
    implementation directly."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"no tool registered under '{name}'") from exc

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return sorted(self._tools)
