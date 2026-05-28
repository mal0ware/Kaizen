"""SKILL.md frontmatter parser + directory loader (ADR 0009).

Format: a ``---``-delimited YAML-style frontmatter block at the top of the
file, then a markdown body. Only simple ``key: value`` scalars are read from
the frontmatter (quoted or bare) — that covers every field in the schema
without pulling in PyYAML.

Bug to guard against: an older parser dropped body content past the first
blank line. Tests pin a multi-section body survives the round-trip intact.
"""
from __future__ import annotations

from pathlib import Path

from kaizen.skills.base import Skill, SkillStatus

_DELIM = "---"


def _parse_frontmatter(block: str) -> dict[str, str]:
    """Tiny ``key: value`` parser. Strips matching surrounding quotes."""
    out: dict[str, str] = {}
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


def parse_skill_md(text: str) -> Skill:
    """Parse a ``SKILL.md`` document into a :class:`Skill`.

    Requires a frontmatter block delimited by ``---`` containing at least
    ``name`` and ``description``. The body is everything after the closing
    delimiter, preserved verbatim (trailing newline stripped).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _DELIM:
        raise ValueError("SKILL.md must start with a '---' frontmatter delimiter")

    close = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _DELIM:
            close = i
            break
    if close is None:
        raise ValueError("SKILL.md frontmatter is not closed by a '---' delimiter")

    fm = _parse_frontmatter("\n".join(lines[1:close]))
    if "name" not in fm or "description" not in fm:
        raise ValueError("SKILL.md frontmatter must define 'name' and 'description'")

    # everything past the closing delimiter is body — preserve it whole
    body = "\n".join(lines[close + 1 :]).lstrip("\n").rstrip()

    status = SkillStatus(fm["status"]) if "status" in fm else SkillStatus.ACTIVE
    return Skill(
        name=fm["name"],
        description=fm["description"],
        body=body,
        source=fm.get("source", "authored"),
        status=status,
    )


def to_skill_md(skill: Skill) -> str:
    """Serialize a :class:`Skill` back to ``SKILL.md`` form."""

    def _emit(key: str, value: str) -> str:
        # quote if value contains a colon or leading/trailing whitespace
        needs_quote = ":" in value or value != value.strip()
        return f'{key}: "{value}"' if needs_quote else f"{key}: {value}"

    fm_lines = [
        _emit("name", skill.name),
        _emit("description", skill.description),
        _emit("source", skill.source),
        _emit("status", skill.status.value),
    ]
    return f"{_DELIM}\n" + "\n".join(fm_lines) + f"\n{_DELIM}\n\n{skill.body}\n"


def load_skills_dir(path: str | Path) -> list[Skill]:
    """Load every ``SKILL.md`` (or ``*.md``) under ``path``."""
    root = Path(path)
    if not root.exists():
        return []
    skills: list[Skill] = []
    seen: set[Path] = set()
    # Prefer canonical SKILL.md; also pick up bare *.md so simple flat layouts work.
    for candidate in sorted(root.rglob("SKILL.md")):
        skills.append(parse_skill_md(candidate.read_text(encoding="utf-8")))
        seen.add(candidate.resolve())
    for candidate in sorted(root.rglob("*.md")):
        if candidate.resolve() in seen or candidate.name == "SKILL.md":
            continue
        try:
            skills.append(parse_skill_md(candidate.read_text(encoding="utf-8")))
        except ValueError:
            # not a skill file (e.g. README.md) — skip silently
            continue
    return skills
