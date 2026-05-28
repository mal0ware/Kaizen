"""End-to-end wiring checks: persona reaches the model, curator proposals
land in the queue, approval applies as a learned trait, and the next prompt
reflects it. Uses the mock provider — no infra needed.
"""
from __future__ import annotations

from kaizen.cli.main import build_agent
from kaizen.core.models import Message, Role
from kaizen.curator.apply import apply_approval


async def test_persona_reaches_the_model_prompt():
    """The system message the loop sends should carry the identity prior."""
    bundle = build_agent()
    user = Message(role=Role.USER, content="hello")
    bundle.session.add(user)

    messages = await bundle.loop.context.build(bundle.session)
    system = next((m for m in messages if m.role is Role.SYSTEM), None)
    assert system is not None
    assert "Kaizen" in system.content
    # Pin a load-bearing phrase from the prior so the test catches accidental
    # replacement of the prior with a generic system_prompt.
    assert "not a helpful assistant" in system.content


async def test_tone_hint_injected_when_non_neutral():
    bundle = build_agent()
    bundle.session.add(Message(role=Role.USER, content="ugh idk man..."))
    messages = await bundle.loop.context.build(bundle.session)
    system = next(m for m in messages if m.role is Role.SYSTEM)
    # Tired tone → "Be brief" hint should land in the system block.
    assert "brief" in system.content.lower()


async def test_curator_proposes_from_repeated_preferences():
    """Three turns of a stated preference should leave the queue with a
    proposal carrying the action."""
    bundle = build_agent()
    for _ in range(3):
        await bundle.loop.handle(
            bundle.session,
            Message(role=Role.USER, content="I always use ruff before committing"),
        )
    # The curator runs in a background task — let the loop drain.
    import asyncio
    await asyncio.sleep(0.05)

    pending = bundle.queue.pending()
    assert pending, "expected the curator to have proposed at least one instinct"
    instinct_proposals = [p for p in pending if p.kind == "instinct"]
    assert instinct_proposals
    actions = " ".join(getattr(p.payload, "action", "") for p in instinct_proposals).lower()
    assert "ruff" in actions


async def test_approval_applies_as_learned_trait_and_persona_picks_it_up():
    bundle = build_agent()
    # Stage a session with a clear preference.
    for _ in range(3):
        await bundle.loop.handle(
            bundle.session,
            Message(role=Role.USER, content="I prefer terse replies, no preamble"),
        )
    import asyncio
    await asyncio.sleep(0.05)

    pending = bundle.queue.pending()
    assert pending
    target = pending[0]

    # Approve and apply.
    bundle.queue.approve(target.id)
    note = apply_approval(target, bundle.learned_traits, bundle.skills)
    assert "learned trait" in note or "skill" in note

    # The next assembled prompt now carries the learned trait.
    bundle.session.add(Message(role=Role.USER, content="next turn"))
    messages = await bundle.loop.context.build(bundle.session)
    system = next(m for m in messages if m.role is Role.SYSTEM)
    assert "Learned voice:" in system.content
    assert any(t.strip("- ").rstrip(".") in system.content for t in bundle.learned_traits)


async def test_proposal_queue_dedupes_repeated_curation_runs():
    """Curator running on every turn must not pile up duplicate proposals for
    the same instinct."""
    bundle = build_agent()
    for _ in range(5):
        await bundle.loop.handle(
            bundle.session,
            Message(role=Role.USER, content="please always run ruff before committing"),
        )
    import asyncio
    await asyncio.sleep(0.05)

    instinct_actions = [
        getattr(p.payload, "action", "").lower()
        for p in bundle.queue.pending()
        if p.kind == "instinct"
    ]
    # The same action should appear at most once in the pending queue.
    assert len(instinct_actions) == len(set(instinct_actions))


async def test_seeded_skills_loaded_into_registry():
    bundle = build_agent()
    names = {s["name"] for s in bundle.skills.specs()}
    assert "search-first" in names
    assert "verification-loop" in names


async def test_persona_disabled_falls_back_to_system_prompt():
    """A test surface that wants a plain system prompt can still get one."""
    from kaizen.core.context import ContextEngine
    from kaizen.memory.inmemory import InMemoryStore
    from kaizen.core.models import Session

    engine = ContextEngine(
        InMemoryStore(),
        system_prompt="plain mode",
        use_persona=False,
    )
    session = Session()
    session.add(Message(role=Role.USER, content="hi"))
    messages = await engine.build(session)
    system = next(m for m in messages if m.role is Role.SYSTEM)
    assert system.content == "plain mode"
