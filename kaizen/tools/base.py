"""Tool interface + registry.

A Tool exposes a name, a description (for the model), and an async `run`. New
capabilities = one module implementing this protocol, registered here.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Tool(Protocol):
    name: str
    description: str

    async def run(self, **kwargs) -> str: ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    def specs(self) -> list[dict]:
        """Model-facing tool descriptions."""
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]
