"""Approval gate — the single chokepoint in front of any write-capable action.

Curator proposals and any future write-capable action submit here; nothing
takes effect until ``approve`` is called by the operator (design-plan §Curator,
ADR 0004). The :class:`~kaizen.curator.proposals.ProposalQueue` composes this
gate rather than duplicating its bookkeeping.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kaizen.curator.proposals import Proposal
    from kaizen.state.base import StateStore


# Action kinds the gate currently considers privileged. Read-only / draft-only
# actions don't pass through here at all; the gate fronts state-changing ones.
_PRIVILEGED_ACTIONS = frozenset(
    {
        "skill.write",
        "skill.archive",
        "memory.edit",
        "memory.delete",
        "instinct.promote",
        "proposal.apply",
    }
)


class ApprovalGate:
    """Pending/approve/reject store. Pass a :class:`StateStore` and the
    pending queue survives restarts — the gate rehydrates from it on
    construction and snapshots after every submit/decision. Without one it
    stays purely in-process (the test default)."""

    def __init__(self, state: StateStore | None = None) -> None:
        self._pending: dict[str, Proposal] = {}
        self._decided: dict[str, Proposal] = {}
        self._state = state
        if state is not None:
            for proposal in state.load_pending():
                self._pending[proposal.id] = proposal

    def _snapshot(self) -> None:
        if self._state is not None:
            self._state.save_pending(list(self._pending.values()))

    def submit(self, proposal: Proposal) -> str:
        self._pending[proposal.id] = proposal
        self._snapshot()
        return proposal.id

    def pending(self) -> list[Proposal]:
        return list(self._pending.values())

    def get(self, proposal_id: str) -> Proposal | None:
        return self._pending.get(proposal_id) or self._decided.get(proposal_id)

    def approve(self, proposal_id: str) -> Proposal:
        from kaizen.curator.proposals import ProposalStatus

        return self._decide(proposal_id, ProposalStatus.APPROVED)

    def reject(self, proposal_id: str) -> Proposal:
        from kaizen.curator.proposals import ProposalStatus

        return self._decide(proposal_id, ProposalStatus.REJECTED)

    def requires_approval(self, action: str) -> bool:
        return action in _PRIVILEGED_ACTIONS

    def _decide(self, proposal_id: str, target):  # type: ignore[no-untyped-def]
        proposal = self._pending.pop(proposal_id, None)
        if proposal is None:
            if proposal_id in self._decided:
                raise ValueError(f"proposal {proposal_id} already decided")
            raise KeyError(f"unknown proposal: {proposal_id}")
        proposal.status = target
        self._decided[proposal_id] = proposal
        self._snapshot()
        return proposal
