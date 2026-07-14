"""Tool interface + registry, run-location, and the transient-error type.

A Tool exposes a name, a description (for the model), an async `run`, and a
`run_location` declaring where it must execute. New capabilities = one module
implementing this protocol, registered here.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Protocol, runtime_checkable


class RunLocation(str, Enum):
    ANY = "any"  # run anywhere (no IP/hardware constraint)
    RESIDENTIAL = "residential"  # must run from a residential IP (e.g., home worker)
    LOCAL_GPU = "local_gpu"  # needs the GPU worker


class TransientToolError(Exception):
    """Recoverable failure (rate limit, IP block, timeout). Signals the
    orchestrator to retry with backoff and/or reroute to another worker —
    distinct from a permanent failure or an empty-but-valid result.
    (See ADR 0009 / the ytmerge lessons.)"""


@runtime_checkable
class Tool(Protocol):
    name: str
    description: str
    run_location: RunLocation

    async def run(self, **kwargs) -> str: ...


def run_location_of(tool: object) -> RunLocation:
    """Where should this tool run? Defaults to ANY if a tool doesn't declare it."""
    return getattr(tool, "run_location", RunLocation.ANY)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    # ``typing.List`` here because the ``list()`` method shadows the builtin
    # ``list`` type within the class body.
    def list(self) -> List[Tool]:
        return list(self._tools.values())

    def specs(self) -> List[dict]:
        """Model-facing tool descriptions."""
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]

    # When the worker pool exists, the orchestrator consults run_location_of(tool)
    # to dispatch a tool to a worker on the right IP/hardware (ADR 0007/0009).
