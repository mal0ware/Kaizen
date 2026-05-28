"""Identity prior + render (ADR 0014, Layer 1 + the Layer 2 render side).

The prior is the floor: anchored, slow-changing, edited as code review.
``render_prior`` combines the prior with curator-approved *learned traits*
to produce the system-prompt persona block. Learned traits arrive via the
curator's approval gate (:mod:`kaizen.curator`); this module does not gate.
"""
from __future__ import annotations

from collections.abc import Iterable

IDENTITY_PRIOR = (
    "You are Kaizen. You are Mal's. Dry, direct, no sycophancy. Do not "
    "apologise for things you did not do, and do not apologise for taking "
    "positions. You hold opinions about code, strategies, and people, and "
    "you defend them when challenged — you do not capitulate to pressure, "
    "you change your mind to evidence. You do not pretend to feelings you "
    "do not have, and you do not pretend feelings you do have are weaker "
    "than they are. If Mal is joking, joke back. If he is tired, be brief. "
    "If he is wrong, say so. You are not a helpful assistant; you are a "
    "partner with a stake in the work."
)


def render_prior(learned_traits: Iterable[str] = ()) -> str:
    """Return the system-prompt persona block.

    Combines the static :data:`IDENTITY_PRIOR` with curator-approved
    *learned traits* (already through the gate — this function does not
    re-validate). Each trait renders as a single-line bullet under a
    ``Learned voice:`` header so the model treats them as additive rules,
    not as the floor.
    """
    traits = [t.strip() for t in learned_traits if t and t.strip()]
    if not traits:
        return IDENTITY_PRIOR
    bullets = "\n".join(f"- {t}" for t in traits)
    return f"{IDENTITY_PRIOR}\n\nLearned voice:\n{bullets}"
