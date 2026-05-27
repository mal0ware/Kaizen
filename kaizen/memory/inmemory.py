"""In-memory store for dev/test — no external infra.

Naive token-overlap scoring stands in for semantic (pgvector) recall (ADR 0002).
The Postgres + pgvector store will implement the same MemoryStore interface.
"""
from __future__ import annotations

from kaizen.memory.base import Fact


class InMemoryStore:
    name = "in-memory"

    def __init__(self) -> None:
        self._facts: list[Fact] = []

    async def add_fact(self, fact: Fact) -> None:
        self._facts.append(fact)

    async def search(self, query: str, k: int = 5) -> list[Fact]:
        terms = [t for t in query.lower().split() if t]
        scored: list[tuple[int, Fact]] = []
        for fact in self._facts:
            haystack = f"{fact.subject} {fact.attribute} {fact.value}".lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, fact))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [fact for _, fact in scored[:k]]
