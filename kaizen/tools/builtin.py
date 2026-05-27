"""Built-in tools that need no network — useful for the dev/mock path.

Real I/O tools (web search, YouTube transcripts, OpenBB, document RAG) implement
the same protocol and live alongside these (ADR 0009).
"""
from __future__ import annotations

from datetime import datetime, timezone

from kaizen.tools.base import RunLocation


class CurrentTimeTool:
    name = "current_time"
    description = "Return the current UTC time as an ISO-8601 string."
    run_location = RunLocation.ANY

    async def run(self, **kwargs) -> str:
        return datetime.now(timezone.utc).isoformat()


class EchoTool:
    name = "echo"
    description = "Echo back the provided text."
    run_location = RunLocation.ANY

    async def run(self, text: str = "", **kwargs) -> str:
        return text
