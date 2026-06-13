"""Skill model + registry (ADR 0009).

Mirrors the ``ToolRegistry`` shape so the loop can consume skill specs the same
way it consumes tool specs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from kaizen.core.models import _now

# ``SkillRegistry.list`` shadows the ``list`` builtin in the class body; alias
# it so ``-> list[Skill]`` annotations resolve to the builtin, not the method.
_SkillList = list


class SkillStatus(str, Enum):
    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"


@dataclass(slots=True)
class Skill:
    name: str
    description: str  # the "when to use" trigger text shown to the model
    body: str  # the procedure itself (markdown)
    source: str = "authored"  # "authored" | "curator" | "imported:<origin>"
    status: SkillStatus = SkillStatus.ACTIVE
    created_at: datetime = field(default_factory=_now)
    last_used_at: datetime | None = None


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list(self) -> _SkillList[Skill]:
        return list(self._skills.values())

    def specs(self) -> _SkillList[dict[str, str]]:
        """Model-facing entries — only active skills."""
        return [
            {"name": s.name, "description": s.description}
            for s in self._skills.values()
            if s.status is SkillStatus.ACTIVE
        ]
