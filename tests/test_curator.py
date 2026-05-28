import pytest

from kaizen.core.models import Message, Role, Session
from kaizen.curator import (
    Curator,
    Instinct,
    InstinctStatus,
    Proposal,
    ProposalQueue,
    ProposalStatus,
)


def test_instinct_defaults():
    i = Instinct(trigger="t", action="a")
    assert i.confidence == 0.5
    assert i.status is InstinctStatus.PENDING
    assert i.source == "session"
    assert (i.last_seen - i.first_seen).total_seconds() < 0.1
    assert i.evidence == []


def test_queue_approve_transition():
    q = ProposalQueue()  # no gate — direct queue inspection
    pid = q.add(Proposal(kind="instinct", payload=Instinct("t", "a"), rationale="r"))
    assert q.pending() and q.pending()[0].id == pid
    approved = q.approve(pid)
    assert approved.status is ProposalStatus.APPROVED
    assert q.pending() == []


def test_queue_reject_transition():
    q = ProposalQueue()
    pid = q.add(Proposal(kind="instinct", payload=Instinct("t", "a"), rationale="r"))
    rejected = q.reject(pid)
    assert rejected.status is ProposalStatus.REJECTED


def test_queue_cannot_double_transition():
    q = ProposalQueue()
    pid = q.add(Proposal(kind="instinct", payload=Instinct("t", "a"), rationale="r"))
    q.approve(pid)
    with pytest.raises(ValueError):
        q.approve(pid)


async def test_review_extracts_preference_proposal():
    session = Session()
    session.add(Message(role=Role.USER, content="I prefer to use tabs over spaces."))
    session.add(Message(role=Role.USER, content="Please always run ruff before committing."))
    curator = Curator()
    proposals = await curator.review(session)
    assert proposals, "expected at least one instinct proposal"
    kinds = {p.kind for p in proposals}
    assert kinds == {"instinct"}
    actions = {p.payload.action.lower() for p in proposals}
    assert any("tabs" in a for a in actions)
    assert any("ruff" in a for a in actions)


async def test_review_confidence_rises_with_repetition():
    session = Session()
    for _ in range(3):
        session.add(Message(role=Role.USER, content="I always use ruff before committing"))
    curator = Curator()
    proposals = await curator.review(session)
    assert proposals
    # 3 hits => 0.4 + 0.15*2 = 0.7
    assert any(p.confidence >= 0.7 - 1e-9 for p in proposals)


async def test_review_ignores_low_confidence_under_threshold():
    session = Session()
    session.add(Message(role=Role.USER, content="some plain question with no preference"))
    curator = Curator()
    assert await curator.review(session) == []


def test_evolve_clusters_into_skill_proposal():
    curator = Curator()
    instincts = [
        Instinct(trigger="ruff lint python", action="run ruff before committing",
                 status=InstinctStatus.ACTIVE, confidence=0.7),
        Instinct(trigger="ruff format python", action="format python with ruff",
                 status=InstinctStatus.ACTIVE, confidence=0.8),
    ]
    proposals = curator.evolve(instincts)
    assert proposals and proposals[0].kind == "skill"
    skill = proposals[0].payload
    assert "ruff" in skill.name or "ruff" in skill.description
    assert proposals[0].confidence == pytest.approx(0.75)


def test_evolve_ignores_inactive_instincts():
    curator = Curator()
    instincts = [
        Instinct(trigger="ruff", action="x", status=InstinctStatus.PENDING),
        Instinct(trigger="ruff", action="y", status=InstinctStatus.PENDING),
    ]
    assert curator.evolve(instincts) == []


async def test_nothing_becomes_active_without_approve():
    """The guarantee that matters: review() never produces ACTIVE state."""
    session = Session()
    session.add(Message(role=Role.USER, content="I always use ruff before committing"))
    proposals = await Curator().review(session)
    assert proposals
    for p in proposals:
        assert p.status is ProposalStatus.PENDING
        if isinstance(p.payload, Instinct):
            assert p.payload.status is InstinctStatus.PENDING
