"""The restart guarantee (scope: persistence).

Approve an instinct proposal, then build a *new* agent against the same state
directory (simulating a process restart): the learned trait must still be
there and must still enter the assembled prompt. Same for pending proposals
and curator-graduated skills.
"""
from __future__ import annotations

import asyncio

from kaizen.bootstrap import build_agent
from kaizen.config import Settings
from kaizen.core.models import Message, Role
from kaizen.curator.apply import apply_approval
from kaizen.curator.instinct import InstinctStatus


def _settings(tmp_path) -> Settings:
    return Settings(state_dir=str(tmp_path))


async def _stage_proposal(bundle) -> None:
    for _ in range(3):
        await bundle.loop.handle(
            bundle.session,
            Message(role=Role.USER, content="I prefer terse replies, no preamble"),
        )
    await asyncio.sleep(0.05)  # curator runs as a background task


async def test_approved_trait_survives_restart_and_enters_prompt(tmp_path):
    first = build_agent(_settings(tmp_path))
    await _stage_proposal(first)
    target = first.queue.pending()[0]
    first.queue.approve(target.id)
    apply_approval(
        target, first.learned_traits, first.skills,
        state=first.state, instincts=first.instincts,
    )
    assert first.learned_traits

    # "Restart": a fresh bundle over the same state dir.
    second = build_agent(_settings(tmp_path))
    assert second.learned_traits == first.learned_traits

    second.session.add(Message(role=Role.USER, content="next turn"))
    messages = await second.loop.context.build(second.session)
    system = next(m for m in messages if m.role is Role.SYSTEM)
    assert "Learned voice:" in system.content


async def test_pending_proposals_survive_restart(tmp_path):
    first = build_agent(_settings(tmp_path))
    await _stage_proposal(first)
    pending_ids = {p.id for p in first.queue.pending()}
    assert pending_ids

    second = build_agent(_settings(tmp_path))
    assert {p.id for p in second.queue.pending()} == pending_ids
    # And the restored queue can still decide them.
    restored = next(iter(pending_ids))
    second.queue.approve(restored)
    assert restored not in {p.id for p in second.queue.pending()}


async def test_approved_instinct_becomes_active_and_survives(tmp_path):
    first = build_agent(_settings(tmp_path))
    await _stage_proposal(first)
    target = first.queue.pending()[0]
    first.queue.approve(target.id)
    apply_approval(
        target, first.learned_traits, first.skills,
        state=first.state, instincts=first.instincts,
    )
    assert first.instincts and first.instincts[0].status is InstinctStatus.ACTIVE

    second = build_agent(_settings(tmp_path))
    assert second.instincts and second.instincts[0].status is InstinctStatus.ACTIVE


async def test_registered_skill_survives_restart(tmp_path):
    from kaizen.curator.proposals import Proposal
    from kaizen.skills.base import Skill

    first = build_agent(_settings(tmp_path))
    skill = Skill(name="terse-replies", description="d", body="b", source="curator")
    proposal = Proposal(kind="skill", payload=skill, rationale="graduated")
    first.queue.add(proposal)
    first.queue.approve(proposal.id)
    apply_approval(
        proposal, first.learned_traits, first.skills,
        state=first.state, instincts=first.instincts,
    )
    assert first.skills.get("terse-replies") is not None

    second = build_agent(_settings(tmp_path))
    assert second.skills.get("terse-replies") is not None
