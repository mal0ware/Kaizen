"""Identity graph node/edge models.

Reputation != reality: an Entity holds objective, Kaizen-observed facts; each
observer's view of a subject lives on a Belief edge keyed by observer.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


def _uid() -> str:
    return uuid.uuid4().hex


@dataclass(slots=True)
class Entity:
    """A real person/thing. May be absent (discussed but never present)."""

    id: str = field(default_factory=_uid)
    display_name: str | None = None
    facts: dict[str, str] = field(default_factory=dict)  # objective, observed


@dataclass(slots=True)
class Account:
    """An observed identity on some platform, linked to an Entity with confidence."""

    id: str = field(default_factory=_uid)
    platform: str = "discord"
    handle: str = ""
    platform_id: str | None = None  # e.g., Discord snowflake (stable)
    entity_id: str | None = None
    link_confidence: float = 0.0


@dataclass(slots=True)
class Belief:
    """An observer's point of view about a subject entity (reputation lives here)."""

    observer_entity_id: str
    subject_entity_id: str
    statement: str
    confidence: float = 0.5
