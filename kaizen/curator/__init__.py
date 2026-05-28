"""Curator: gated self-improvement (design-plan §Curator, ADR 0004).

A background pass reviews sessions and *proposes* changes — new/updated
skills, memory edits, graduated instincts. Every proposal routes through the
:class:`~kaizen.safety.gate.ApprovalGate`; nothing self-applies. Skills move
through active/stale/archive so they don't pile up (ADR 0009).
"""
from kaizen.curator.instinct import Instinct, InstinctStatus
from kaizen.curator.proposals import Proposal, ProposalQueue, ProposalStatus
from kaizen.curator.review import Curator

__all__ = [
    "Curator",
    "Instinct",
    "InstinctStatus",
    "Proposal",
    "ProposalQueue",
    "ProposalStatus",
]
