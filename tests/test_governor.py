from kaizen.core.models import Message, Role
from kaizen.realtime.governor import GovernorConfig, InterjectionGovernor


def test_addressed_always_responds():
    g = InterjectionGovernor()
    assert g.should_respond(Message(role=Role.USER, content="anything"), [], addressed=True)


def test_does_not_respond_to_non_user():
    g = InterjectionGovernor()
    assert not g.should_respond(Message(role=Role.ASSISTANT, content="x"), [])


def test_pre_send_recheck_drops_stale_draft():
    g = InterjectionGovernor(GovernorConfig(min_relevance=0.5))
    latest = [Message(role=Role.USER, content="completely different topic now")]
    assert not g.still_relevant("apples and oranges", latest)


def test_pre_send_recheck_keeps_relevant_draft():
    g = InterjectionGovernor(GovernorConfig(min_relevance=0.2))
    latest = [Message(role=Role.USER, content="tell me about trading risk")]
    assert g.still_relevant("trading risk matters", latest)
