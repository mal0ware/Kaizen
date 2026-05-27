"""Provider interface + request/response types.

A Provider turns a list of messages into a completion (text and/or tool calls).
The agent loop only ever talks to this interface, so backends — cloud API,
Claude-Code auth, or a local engine — are interchangeable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

from kaizen.core.models import Message, ToolCall


class Tier(int, Enum):
    LOCAL = 0  # free, high-volume (home GPU)
    CHEAP = 1  # cheap cloud
    FRONTIER = 2  # frontier, rare / hard


@dataclass(slots=True)
class CompletionRequest:
    messages: list[Message]
    tools: list[dict] = field(default_factory=list)
    max_tokens: int = 1024
    extended_thinking: bool = False


@dataclass(slots=True)
class CompletionResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = "unknown"
    input_tokens: int = 0
    output_tokens: int = 0


@runtime_checkable
class Provider(Protocol):
    name: str
    tier: Tier

    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...
