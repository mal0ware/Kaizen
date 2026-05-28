"""Budget-guard defaults.

ECC-derived constants for the cost knobs the router and context compressor
already exist to enforce (ADR 0006 / 0008). Kept as plain module constants
so they're trivial to import and override per-deployment; the router itself
is not restructured — it's already deeper than ECC's config-only equivalent
(see docs/research/ecc-evaluation-and-integration.md §4).
"""
from __future__ import annotations

from kaizen.providers.base import Tier

# Cap on the "extended thinking" token budget per request. ECC settled on
# ~10k after empirical context-bloat testing; above that, quality returns
# flatten and context fills up.
MAX_THINKING_TOKENS = 10_000

# Trigger context compaction at this fill ratio, not at the harness's default
# ~95% — earlier compaction lands at logical breakpoints (post-research,
# post-milestone) instead of mid-implementation.
EARLY_COMPACT_PCT = 0.50

# Subagent-class work (delegated planning, code review, summarization) should
# prefer the cheap local tier — frontier dollars are for the operator-facing
# main thread, not for fan-out.
SUBAGENT_TIER_HINT: Tier = Tier.LOCAL

# Voice canonicalization (ADR 0014, Layer 4). Operator-facing speech is pinned
# to a single tier so the persona stays consistent across turns — small local
# models do reasoning/grunt work, the frontier handles speech. The router
# consults this for any reply destined to the operator surface; everything
# else is freely routed by difficulty.
OPERATOR_VOICE_TIER: Tier = Tier.FRONTIER
