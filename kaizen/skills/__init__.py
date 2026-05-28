"""Skills: saved, reusable procedures the curator authors and the loop surfaces.

Skills are stored as ``SKILL.md`` files — a YAML-style frontmatter block (at
minimum ``name:`` and ``description:``) followed by a markdown body that
contains the procedure. The format is intentionally compatible with the open
skill ecosystem (Anthropic's official skills, ECC's catalog) so external skills
can be ingested as a menu (ADR 0009; design-plan §Tools & skills).

Lifecycle: ``ACTIVE`` → ``STALE`` → ``ARCHIVED``. Only active skills are
surfaced to the model via :py:meth:`SkillRegistry.specs`.
"""
from kaizen.skills.base import Skill, SkillRegistry, SkillStatus
from kaizen.skills.loader import load_skills_dir, parse_skill_md, to_skill_md

__all__ = [
    "Skill",
    "SkillRegistry",
    "SkillStatus",
    "load_skills_dir",
    "parse_skill_md",
    "to_skill_md",
]
