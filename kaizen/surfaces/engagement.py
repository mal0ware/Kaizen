"""Engagement decision for ambient surfaces (ADR 0005).

Pure logic, no discord import — the Discord surface feeds it flags, the tests
feed it directly. Being addressed (DM, mention, reply) always engages; an
open "active conversation" window is no longer a blank check — the
:class:`~kaizen.realtime.governor.InterjectionGovernor` judges whether the
message is still relevant enough to speak to.
"""
from __future__ import annotations

from dataclasses import dataclass

from kaizen.core.models import Message
from kaizen.realtime.governor import InterjectionGovernor


@dataclass(slots=True)
class EngagementContext:
    is_dm: bool = False
    mentioned: bool = False
    is_reply_to_bot: bool = False
    in_active_window: bool = False


def should_engage(
    ctx: EngagementContext,
    incoming: Message,
    recent: list[Message],
    governor: InterjectionGovernor,
) -> bool:
    if ctx.is_dm or ctx.mentioned or ctx.is_reply_to_bot:
        return True
    if not ctx.in_active_window:
        return False
    return governor.should_respond(incoming, recent, addressed=False)
