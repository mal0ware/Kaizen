"""Context engine: assembles the message list sent to a model.

Skeleton = system prompt + naive memory recall + recent turns. Compression and
semantic (pgvector) recall arrive later (ADR 0002); the interface stays the same.
"""
from __future__ import annotations

from kaizen.core.models import Message, Role, Session
from kaizen.memory.base import MemoryStore


class ContextEngine:
    def __init__(self, memory: MemoryStore, system_prompt: str = "", max_turns: int = 20):
        self.memory = memory
        self.system_prompt = system_prompt
        self.max_turns = max_turns

    async def build(self, session: Session) -> list[Message]:
        messages: list[Message] = []
        if self.system_prompt:
            messages.append(Message(role=Role.SYSTEM, content=self.system_prompt))

        last_user = next(
            (m for m in reversed(session.messages) if m.role == Role.USER), None
        )
        if last_user:
            facts = await self.memory.search(last_user.content, k=5)
            if facts:
                recalled = "; ".join(f.value for f in facts)
                messages.append(
                    Message(role=Role.SYSTEM, content=f"Relevant memory: {recalled}")
                )

        messages.extend(session.recent(self.max_turns))
        return messages
