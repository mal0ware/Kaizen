"""The scribe — ambient learning (ADR 0002).

After each exchange it looks at the new turns, asks the local model to extract
durable facts about the user, and writes them to memory. The context engine then
surfaces relevant facts in later turns, so Kaizen *remembers* and *grows* —
without the user having to "teach" it deliberately. Runs in the background
(non-blocking) and is built to never break the conversation if extraction fails.
"""
from __future__ import annotations

import json
import re

from kaizen.core.models import Message, Role, Session
from kaizen.memory.base import Fact, MemoryStore
from kaizen.providers.base import CompletionRequest, Provider

EXTRACTION_PROMPT = (
    'You extract durable, long-term facts about the user from a conversation. '
    'Output ONLY a JSON array of objects with keys "subject", "attribute", "value". '
    'Use "user" as the subject for facts about the person you are talking to. '
    "Capture stable things — preferences, projects, goals, identity, relationships — "
    "and skip small talk. If there is nothing worth remembering, output []."
)


def parse_facts(text: str) -> list[Fact]:
    """Pull a JSON array of facts out of model output, defensively."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return []
    facts: list[Fact] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and str(item.get("value", "")).strip():
                facts.append(
                    Fact(
                        subject=str(item.get("subject") or "user"),
                        attribute=str(item.get("attribute", "")),
                        value=str(item.get("value", "")).strip(),
                        source="scribe",
                        confidence=0.6,
                    )
                )
    return facts


class Scribe:
    def __init__(
        self,
        provider: Provider,
        memory: MemoryStore,
        min_new_user_msgs: int = 1,
        max_seen: int = 4096,
        max_sessions: int = 256,
    ):
        self.provider = provider
        self.memory = memory
        self.min_new = min_new_user_msgs
        self.max_seen = max_seen
        self.max_sessions = max_sessions
        # Both caches are bounded (dicts keep insertion order, so eviction is
        # oldest-first): a long-lived daemon must not grow them forever. An
        # evicted _seen key at worst re-stores a duplicate fact — harmless.
        self._watermark: dict[str, int] = {}
        self._seen: dict[tuple[str, str, str], None] = {}

    async def observe(self, session: Session) -> None:
        """Extract facts from turns added since last time, and store new ones.
        Swallows all errors — the scribe must never break the conversation."""
        try:
            start = self._watermark.get(session.id, 0)
            new = session.messages[start:]
            if sum(1 for m in new if m.role == Role.USER) < self.min_new:
                return
            # Re-insert so the most recently active session evicts last.
            self._watermark.pop(session.id, None)
            self._watermark[session.id] = len(session.messages)
            while len(self._watermark) > self.max_sessions:
                self._watermark.pop(next(iter(self._watermark)))

            for fact in await self._extract(new):
                key = (fact.subject, fact.attribute, fact.value)
                if key in self._seen:
                    continue
                self._seen[key] = None
                while len(self._seen) > self.max_seen:
                    self._seen.pop(next(iter(self._seen)))
                await self.memory.add_fact(fact)
        except Exception:
            return

    async def _extract(self, messages: list[Message]) -> list[Fact]:
        transcript = "\n".join(f"{m.role.value}: {m.content}" for m in messages if m.content)
        if not transcript.strip():
            return []
        request = CompletionRequest(
            messages=[
                Message(role=Role.SYSTEM, content=EXTRACTION_PROMPT),
                Message(role=Role.USER, content=transcript),
            ],
            max_tokens=512,
        )
        response = await self.provider.complete(request)
        return parse_facts(response.text)
