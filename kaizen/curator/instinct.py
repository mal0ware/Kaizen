"""Instincts: confidence-scored, gated learnings extracted from sessions.

Modeled on the ``Fact`` shape (memory/base.py) for consistency — same
confidence/source/first_seen/last_seen plumbing. An instinct is the curator's
internal unit of learning; it becomes effective only after the operator
approves a :class:`~kaizen.curator.proposals.Proposal` that carries it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from kaizen.core.models import _now


class InstinctStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(slots=True)
class Instinct:
    trigger: str  # what cues this — a short phrase / keyword set
    action: str  # what to do when the cue fires
    confidence: float = 0.5
    source: str = "session"  # "session" | "operator" | "imported:<origin>"
    status: InstinctStatus = InstinctStatus.PENDING
    evidence: list[str] = field(default_factory=list)  # session ids / message excerpts
    first_seen: datetime = field(default_factory=_now)
    last_seen: datetime = field(default_factory=_now)
