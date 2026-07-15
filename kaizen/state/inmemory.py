"""In-memory state store — the zero-side-effect default for tests.

Round-trips every save through the same serde as the file store, so anything
that persists in tests is guaranteed JSON-serializable in production too.
"""
from __future__ import annotations

from typing import Any

from kaizen.core.models import Session
from kaizen.curator.instinct import Instinct
from kaizen.curator.proposals import Proposal
from kaizen.skills.base import Skill
from kaizen.state import serde


class InMemoryStateStore:
    name = "inmemory-state"

    def __init__(self) -> None:
        self._data: dict[str, list[Any]] = {}

    def load_traits(self) -> list[str]:
        return list(self._data.get("traits", []))

    def save_traits(self, traits: list[str]) -> None:
        self._data["traits"] = list(traits)

    def load_skills(self) -> list[Skill]:
        return [serde.skill_from_dict(d) for d in self._data.get("skills", [])]

    def save_skills(self, skills: list[Skill]) -> None:
        self._data["skills"] = [serde.skill_to_dict(s) for s in skills]

    def load_instincts(self) -> list[Instinct]:
        return [serde.instinct_from_dict(d) for d in self._data.get("instincts", [])]

    def save_instincts(self, instincts: list[Instinct]) -> None:
        self._data["instincts"] = [serde.instinct_to_dict(i) for i in instincts]

    def load_pending(self) -> list[Proposal]:
        return [serde.proposal_from_dict(d) for d in self._data.get("proposals", [])]

    def save_pending(self, proposals: list[Proposal]) -> None:
        self._data["proposals"] = [serde.proposal_to_dict(p) for p in proposals]

    def load_sessions(self) -> list[Session]:
        return [serde.session_from_dict(d) for d in self._data.get("sessions", [])]

    def save_sessions(self, sessions: list[Session]) -> None:
        self._data["sessions"] = [serde.session_to_dict(s) for s in sessions]
