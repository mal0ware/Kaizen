"""Memory interface + the Fact model.

A Fact is a typed, sourced, confidence-scored, time-stamped unit of knowledge —
so individual facts update in place, decay, and resolve conflicts by recency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class Fact:
    subject: str
    attribute: str
    value: str
    confidence: float = 0.5
    source: str = "observed"
    first_seen: datetime = field(default_factory=_now)
    last_seen: datetime = field(default_factory=_now)


@runtime_checkable
class MemoryStore(Protocol):
    name: str

    async def add_fact(self, fact: Fact) -> None: ...
    async def search(self, query: str, k: int = 5) -> list[Fact]: ...
