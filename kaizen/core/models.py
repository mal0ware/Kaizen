"""Core domain models: messages, tool calls, and sessions.

Plain dataclasses (no heavy deps) so the core imports cleanly anywhere.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid() -> str:
    return uuid.uuid4().hex


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(slots=True)
class ToolCall:
    name: str
    arguments: dict = field(default_factory=dict)
    id: str = field(default_factory=_uid)  # ties a tool result back to its request


@dataclass(slots=True)
class Message:
    role: Role
    content: str = ""
    author_id: str | None = None  # stable platform id (e.g., Discord snowflake)
    name: str | None = None  # display name, or tool name for TOOL messages
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None  # on a TOOL message: which ToolCall it answers
    created_at: datetime = field(default_factory=_now)


@dataclass(slots=True)
class Session:
    """A conversation owned by the core. Surfaces attach to it; it outlives them."""

    id: str = field(default_factory=_uid)
    surface: str = "cli"
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=_now)

    def add(self, message: Message) -> Message:
        self.messages.append(message)
        return message

    def recent(self, n: int = 20) -> list[Message]:
        return self.messages[-n:]
