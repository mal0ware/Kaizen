"""Context engine: assembles the message list sent to a model.

Builds: persona block (ADR 0014 — identity prior + curator-approved learned
traits + per-turn tone hint) → memory recall (ADR 0002) → recent turns.
Compression and semantic (pgvector) recall arrive later; the interface stays
the same.
"""
from __future__ import annotations

from kaizen.core.models import Message, Role, Session
from kaizen.memory.base import MemoryStore
from kaizen.persona import classify_tone, render_prior, tone_hint


class ContextEngine:
    def __init__(
        self,
        memory: MemoryStore,
        system_prompt: str | None = None,
        learned_traits: list[str] | None = None,
        use_persona: bool = True,
        max_turns: int = 20,
    ):
        self.memory = memory
        # ``system_prompt`` overrides persona when explicitly set; otherwise the
        # persona stack composes the system block. ``learned_traits`` is a
        # mutable list shared with the operator-side approval handler — when a
        # proposal is approved, the new trait is appended here and takes
        # effect on the next ``build()`` without restarting the agent.
        self.system_prompt = system_prompt
        self.learned_traits = learned_traits if learned_traits is not None else []
        self.use_persona = use_persona
        self.max_turns = max_turns

    def _system_block(self, session: Session) -> str:
        if not self.use_persona and self.system_prompt:
            return self.system_prompt
        prior = render_prior(self.learned_traits)
        tone = classify_tone(session.messages)
        hint = tone_hint(tone)
        return f"{prior}\n\n{hint}" if hint else prior

    async def build(self, session: Session) -> list[Message]:
        messages: list[Message] = []
        block = self._system_block(session)
        if block:
            messages.append(Message(role=Role.SYSTEM, content=block))

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
