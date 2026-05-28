"""Safety: the approval gate and ingest-time redaction.

The :class:`~kaizen.safety.gate.ApprovalGate` is the single chokepoint in
front of any write-capable action — curator proposals route through it and
nothing self-applies (design-plan §Curator, ADR 0004).
:func:`~kaizen.safety.redact.redact` strips common credential shapes from
content before it reaches the scribe or identity graph.
"""
from kaizen.safety.gate import ApprovalGate
from kaizen.safety.redact import redact, scrub_message

__all__ = ["ApprovalGate", "redact", "scrub_message"]
