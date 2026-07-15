"""Engagement decision tests — the governor finally sits in the message path."""
from __future__ import annotations

from kaizen.core.models import Message, Role
from kaizen.realtime.governor import GovernorConfig, InterjectionGovernor
from kaizen.surfaces.engagement import EngagementContext, should_engage


def _msg(content: str) -> Message:
    return Message(role=Role.USER, content=content)


def _governor(talkativeness: float = 0.5) -> InterjectionGovernor:
    return InterjectionGovernor(GovernorConfig(talkativeness=talkativeness))


def test_dm_always_engages():
    ctx = EngagementContext(is_dm=True)
    assert should_engage(ctx, _msg("anything at all"), [], _governor())


def test_mention_always_engages():
    ctx = EngagementContext(mentioned=True)
    assert should_engage(ctx, _msg("hey you"), [], _governor())


def test_reply_to_bot_always_engages():
    ctx = EngagementContext(is_reply_to_bot=True)
    assert should_engage(ctx, _msg("re: that"), [], _governor())


def test_outside_window_unaddressed_stays_silent():
    ctx = EngagementContext()  # nothing set
    assert not should_engage(ctx, _msg("very relevant trading talk"), [], _governor())


def test_in_window_relevant_message_engages():
    ctx = EngagementContext(in_active_window=True)
    recent = [_msg("we were discussing trading risk and hedging")]
    assert should_engage(ctx, _msg("trading risk again"), recent, _governor())


def test_in_window_irrelevant_message_absorbed():
    """The governor's whole point: an open window is no longer a blank check."""
    ctx = EngagementContext(in_active_window=True)
    recent = [_msg("we were discussing trading risk and hedging")]
    assert not should_engage(ctx, _msg("zebras enjoy marmalade"), recent, _governor())
