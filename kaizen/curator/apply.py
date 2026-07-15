"""Post-approval application — what actually happens when a proposal is approved.

The :class:`~kaizen.safety.gate.ApprovalGate` records the decision; this module
is the operator-side handler that turns an approved :class:`Proposal` into a
*change to Kaizen's own state*. Per the trust model (feedback memory:
agent-agency), the gate exists for self-state mutations only — Kaizen's
actions *in the world* do not pass through here.

Effects today:
- ``instinct`` approval -> mark the instinct ACTIVE (so the curator's evolve
  pass can graduate it into a skill later) and append a one-line trait to
  ``learned_traits``; the context engine picks it up on the next prompt build
  (ADR 0014, Layer 2).
- ``skill`` approval -> register the skill in :class:`SkillRegistry`;
  ``specs()`` then exposes it to the model.
- ``memory_edit`` approval -> reserved; not handled yet.

Pass ``state`` (and ``instincts``) to persist each effect through the
:class:`~kaizen.state.base.StateStore`; without them the effects stay
in-process, as before.
"""
from __future__ import annotations

from kaizen.curator.instinct import Instinct, InstinctStatus
from kaizen.curator.proposals import Proposal
from kaizen.skills.base import Skill, SkillRegistry
from kaizen.state.base import StateStore


def trait_from_instinct(inst: Instinct) -> str:
    """Render a learned-trait sentence the model can act on."""
    return f"When relevant ({inst.trigger}): {inst.action}."


def apply_approval(
    proposal: Proposal,
    learned_traits: list[str],
    skills: SkillRegistry,
    state: StateStore | None = None,
    instincts: list[Instinct] | None = None,
) -> str:
    """Apply an approved proposal. Returns a one-line summary for display.

    Caller is expected to have already invoked ``gate.approve`` (or
    ``queue.approve``) — this function does not re-check status.
    """
    payload = proposal.payload
    if isinstance(payload, Instinct):
        payload.status = InstinctStatus.ACTIVE
        if instincts is not None and payload not in instincts:
            instincts.append(payload)
        trait = trait_from_instinct(payload)
        if trait not in learned_traits:
            learned_traits.append(trait)
        if state is not None:
            state.save_traits(learned_traits)
            if instincts is not None:
                state.save_instincts(instincts)
        return f"learned trait added: {trait}"
    if isinstance(payload, Skill):
        skills.register(payload)
        if state is not None:
            state.save_skills([s for s in skills.list() if s.source == "curator"])
        return f"skill registered: {payload.name}"
    return f"approved ({proposal.kind}) — no application handler"
