from kaizen.core.models import Message, Role
from kaizen.orchestration.router import Difficulty, Router, triage
from kaizen.providers.base import Tier
from kaizen.providers.mock import MockProvider


def test_triage_easy():
    assert triage(Message(role=Role.USER, content="hi there")) == Difficulty.EASY


def test_triage_hard_on_keyword():
    assert triage(Message(role=Role.USER, content="analyze this trade risk")) == Difficulty.HARD


def test_router_picks_target_tier():
    mock = MockProvider()
    router = Router({Tier.LOCAL: mock, Tier.FRONTIER: mock})
    assert router.choose(Difficulty.EASY) is mock


def test_router_falls_back_when_tier_missing():
    mock = MockProvider()
    router = Router({Tier.LOCAL: mock})  # no cloud/frontier available
    # HARD wants FRONTIER, but only LOCAL exists -> fall back to LOCAL
    assert router.choose(Difficulty.HARD) is mock
