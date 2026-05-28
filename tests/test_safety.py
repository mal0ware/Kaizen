import pytest

from kaizen.core.models import Message, Role
from kaizen.curator.instinct import Instinct
from kaizen.curator.proposals import Proposal, ProposalQueue, ProposalStatus
from kaizen.safety import ApprovalGate, redact, scrub_message


def test_redact_openai_sk_key():
    out = redact("token is sk-abcDEF1234567890ABCDEFGH and more text")
    assert "sk-abcDEF" not in out
    assert "«redacted:openai-key»" in out
    assert "and more text" in out


def test_redact_anthropic_sk_ant_key():
    out = redact("ANTHROPIC_API_KEY=sk-ant-api03-aaaaaaaaaaaaaaaaaaaa1234567890")
    assert "sk-ant" not in out
    assert "«redacted:openai-key»" in out


def test_redact_github_pat():
    out = redact("uses ghp_" + "A" * 36 + " here")
    assert "ghp_" not in out
    assert "«redacted:github-token»" in out


def test_redact_github_fine_grained_pat():
    out = redact("token github_pat_" + "A" * 60)
    assert "github_pat_" not in out
    assert "«redacted:github-token»" in out


def test_redact_aws_key():
    out = redact("creds AKIAIOSFODNN7EXAMPLE rotated")
    assert "AKIA" not in out
    assert "«redacted:aws-key»" in out


def test_redact_bearer_keeps_word_redacts_token():
    out = redact("Authorization: Bearer abc123def456ghi789jkl012")
    assert "Bearer" in out
    assert "abc123def456ghi789jkl012" not in out
    assert "«redacted:bearer»" in out


def test_redact_leaves_normal_prose_alone():
    text = "The quick brown fox jumps over the lazy dog. Mal prefers tabs."
    assert redact(text) == text


def test_redact_empty_input():
    assert redact("") == ""


def test_scrub_message_preserves_fields():
    msg = Message(role=Role.USER, content="key sk-abcDEF1234567890ABCDEFGH end", author_id="u1")
    scrubbed = scrub_message(msg)
    assert scrubbed.role is Role.USER
    assert scrubbed.author_id == "u1"
    assert "sk-abc" not in scrubbed.content
    # original is untouched
    assert "sk-abc" in msg.content


def test_gate_blocks_until_approve():
    gate = ApprovalGate()
    proposal = Proposal(kind="instinct", payload=Instinct("t", "a"), rationale="r")
    pid = gate.submit(proposal)
    assert gate.pending() and gate.pending()[0].id == pid
    decided = gate.approve(pid)
    assert decided.status is ProposalStatus.APPROVED
    assert gate.pending() == []


def test_gate_reject():
    gate = ApprovalGate()
    pid = gate.submit(Proposal(kind="instinct", payload=Instinct("t", "a"), rationale="r"))
    rejected = gate.reject(pid)
    assert rejected.status is ProposalStatus.REJECTED


def test_gate_rejects_double_decide():
    gate = ApprovalGate()
    pid = gate.submit(Proposal(kind="instinct", payload=Instinct("t", "a"), rationale="r"))
    gate.approve(pid)
    with pytest.raises(ValueError):
        gate.approve(pid)


def test_gate_unknown_proposal():
    gate = ApprovalGate()
    with pytest.raises(KeyError):
        gate.approve("does-not-exist")


def test_gate_requires_approval_policy():
    gate = ApprovalGate()
    assert gate.requires_approval("memory.edit")
    assert gate.requires_approval("instinct.promote")
    assert not gate.requires_approval("memory.read")


def test_proposal_queue_routes_through_gate():
    gate = ApprovalGate()
    queue = ProposalQueue(gate=gate)
    pid = queue.add(Proposal(kind="instinct", payload=Instinct("t", "a"), rationale="r"))
    # Queue submitted to the gate — both see it pending.
    assert any(p.id == pid for p in queue.pending())
    assert any(p.id == pid for p in gate.pending())
    queue.approve(pid)
    # Both reflect the decision; gate is the single chokepoint.
    assert gate.pending() == []
    assert queue.pending() == []
