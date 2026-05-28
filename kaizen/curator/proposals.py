"""Proposal queue — the single channel the curator pushes work through.

A proposal is the curator's offer to change something: a new skill, a memory
edit, or a graduated instinct. Nothing here self-applies; the
:class:`~kaizen.safety.gate.ApprovalGate` is the only path to effect, and
this queue composes it (does not duplicate it) so the gate stays the single
chokepoint (design-plan §Curator, ADR 0004).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from kaizen.core.models import _now, _uid

if TYPE_CHECKING:
    from kaizen.safety.gate import ApprovalGate

ProposalKind = Literal["skill", "memory_edit", "instinct"]


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(slots=True)
class Proposal:
    kind: ProposalKind
    payload: Any  # a Skill / Instinct / dict, depending on kind
    rationale: str
    confidence: float = 0.5
    status: ProposalStatus = ProposalStatus.PENDING
    id: str = field(default_factory=_uid)
    created_at: datetime = field(default_factory=_now)


def _fingerprint(proposal: Proposal) -> tuple | None:
    """Stable key for deduping equivalent pending proposals. ``None`` = no
    dedup (each ``add`` creates a new entry)."""
    payload = proposal.payload
    trigger = getattr(payload, "trigger", None)
    action = getattr(payload, "action", None)
    if trigger and action:
        return ("instinct", str(trigger).lower().strip(), str(action).lower().strip())
    name = getattr(payload, "name", None)
    if name:
        return (proposal.kind, str(name).lower().strip())
    return None


class ProposalQueue:
    """Submission + state for curator proposals.

    Routes ``add``/``approve``/``reject`` through an :class:`ApprovalGate` so
    every proposal passes the same chokepoint as any other write-capable
    action. Pass ``gate=None`` only in tests that want to inspect the queue
    in isolation.

    Duplicate pending proposals (same payload fingerprint) are folded onto
    the existing entry — the curator runs every turn, and without dedup the
    operator would see the same instinct piling up.
    """

    def __init__(self, gate: ApprovalGate | None = None) -> None:
        self._proposals: dict[str, Proposal] = {}
        self._gate = gate
        self._by_fingerprint: dict[tuple, str] = {}

    def add(self, proposal: Proposal) -> str:
        fp = _fingerprint(proposal)
        if fp is not None and fp in self._by_fingerprint:
            existing_id = self._by_fingerprint[fp]
            existing = self._proposals.get(existing_id)
            if existing is not None and existing.status is ProposalStatus.PENDING:
                # Lift confidence to the higher of the two so re-observed
                # patterns gain weight without spawning a new card.
                if proposal.confidence > existing.confidence:
                    existing.confidence = proposal.confidence
                return existing_id
        self._proposals[proposal.id] = proposal
        if fp is not None:
            self._by_fingerprint[fp] = proposal.id
        if self._gate is not None:
            self._gate.submit(proposal)
        return proposal.id

    def get(self, proposal_id: str) -> Proposal | None:
        return self._proposals.get(proposal_id)

    def pending(self) -> list[Proposal]:
        return [p for p in self._proposals.values() if p.status is ProposalStatus.PENDING]

    def approve(self, proposal_id: str) -> Proposal:
        if self._gate is not None:
            return self._gate.approve(proposal_id)
        return self._transition(proposal_id, ProposalStatus.APPROVED)

    def reject(self, proposal_id: str) -> Proposal:
        if self._gate is not None:
            return self._gate.reject(proposal_id)
        return self._transition(proposal_id, ProposalStatus.REJECTED)

    def _transition(self, proposal_id: str, target: ProposalStatus) -> Proposal:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise KeyError(f"unknown proposal: {proposal_id}")
        if proposal.status is not ProposalStatus.PENDING:
            raise ValueError(
                f"proposal {proposal_id} is {proposal.status.value}, cannot transition"
            )
        proposal.status = target
        return proposal
