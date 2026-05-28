from pathlib import Path

from kaizen.skills import (
    Skill,
    SkillRegistry,
    SkillStatus,
    load_skills_dir,
    parse_skill_md,
    to_skill_md,
)

_EXAMPLES = Path(__file__).resolve().parent.parent / "kaizen" / "skills" / "examples"


def test_parse_basic_frontmatter():
    text = """---
name: foo
description: a short trigger
---

# Heading

Body text.
"""
    skill = parse_skill_md(text)
    assert skill.name == "foo"
    assert skill.description == "a short trigger"
    assert "Body text." in skill.body
    assert skill.status is SkillStatus.ACTIVE


def test_frontmatter_body_loss_regression():
    """A multi-section body must survive parsing intact — past blank lines and
    past headings. The older parser truncated everything after the first blank
    line; pin that behaviour out."""
    text = """---
name: multi
description: multi-section body
---

# Section 1

First paragraph.

## Section 2

Second paragraph after a blank line.

```python
print("code block survives too")
```

Trailing paragraph.
"""
    skill = parse_skill_md(text)
    assert "Section 1" in skill.body
    assert "Section 2" in skill.body
    assert "code block survives too" in skill.body
    assert "Trailing paragraph." in skill.body


def test_round_trip_parse_serialize():
    original = Skill(
        name="rt",
        description="round trip test",
        body="# Body\n\nKeep me.",
        status=SkillStatus.ACTIVE,
    )
    text = to_skill_md(original)
    parsed = parse_skill_md(text)
    assert parsed.name == original.name
    assert parsed.description == original.description
    assert parsed.body.strip() == original.body.strip()
    assert parsed.status is original.status


def test_quoted_description_with_colon():
    text = '---\nname: q\ndescription: "uses: a colon inside"\n---\n\nbody\n'
    skill = parse_skill_md(text)
    assert skill.description == "uses: a colon inside"


def test_missing_frontmatter_rejected():
    import pytest

    with pytest.raises(ValueError):
        parse_skill_md("no frontmatter here")


def test_registry_specs_excludes_non_active():
    reg = SkillRegistry()
    reg.register(Skill(name="a", description="active one", body="b"))
    reg.register(
        Skill(name="b", description="archived one", body="b", status=SkillStatus.ARCHIVED)
    )
    reg.register(Skill(name="c", description="stale one", body="b", status=SkillStatus.STALE))
    specs = reg.specs()
    names = {s["name"] for s in specs}
    assert names == {"a"}


def test_load_skills_dir_finds_seeded_examples():
    skills = load_skills_dir(_EXAMPLES)
    names = {s.name for s in skills}
    assert "search-first" in names
    assert "verification-loop" in names
    # bodies came through with their procedural content
    sf = next(s for s in skills if s.name == "search-first")
    assert "Procedure" in sf.body


def test_load_skills_dir_missing_path_returns_empty(tmp_path):
    assert load_skills_dir(tmp_path / "nope") == []
