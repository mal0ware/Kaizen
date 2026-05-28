"""Persona: the four-layer voice stack (ADR 0014).

Operator-facing speech is composed by combining:

1. :mod:`kaizen.persona.prior` — the identity prior (Layer 1, floor).
2. Curator-approved **learned traits**, folded into the prior at render time
   (Layer 2; the authoring side lives in :mod:`kaizen.curator`).
3. :mod:`kaizen.persona.tone` — per-turn tone classification (Layer 3).
4. Voice canonicalization (Layer 4) — a router concern; see
   ``OPERATOR_VOICE_TIER`` in :mod:`kaizen.orchestration.budgets`.

This module owns layers 1 and 3. Layer 2 plumbing lives in the curator; this
module exposes the *render* side (taking approved traits + the prior and
emitting a system-prompt block). Layer 4 is enforced by the router.
"""
from kaizen.persona.prior import IDENTITY_PRIOR, render_prior
from kaizen.persona.tone import ToneTag, classify_tone, tone_hint

__all__ = [
    "IDENTITY_PRIOR",
    "ToneTag",
    "classify_tone",
    "render_prior",
    "tone_hint",
]
