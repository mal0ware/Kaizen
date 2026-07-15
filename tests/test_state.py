"""State-store tests: serde round-trips, atomic file persistence, and the
restart guarantee — approved traits/skills/proposals survive a new store
instance pointed at the same directory."""
from __future__ import annotations

from datetime import datetime

from kaizen.config import Settings
from kaizen.core.models import Message, Role, Session, ToolCall
from kaizen.curator.instinct import Instinct, InstinctStatus
from kaizen.curator.proposals import Proposal, ProposalStatus
from kaizen.skills.base import Skill, SkillStatus
from kaizen.state import FileStateStore, InMemoryStateStore, build_state
from kaizen.state.serde import (
    proposal_from_dict,
    proposal_to_dict,
    session_from_dict,
    session_to_dict,
)


# --- serde round-trips -------------------------------------------------------


def test_proposal_roundtrip_instinct_payload():
    instinct = Instinct(
        trigger="ruff lint",
        action="run ruff before committing",
        confidence=0.7,
        status=InstinctStatus.ACTIVE,
        evidence=["I always run ruff"],
    )
    proposal = Proposal(kind="instinct", payload=instinct, rationale="seen twice", confidence=0.7)
    restored = proposal_from_dict(proposal_to_dict(proposal))
    assert restored.id == proposal.id
    assert restored.kind == "instinct"
    assert restored.status is ProposalStatus.PENDING
    assert isinstance(restored.payload, Instinct)
    assert restored.payload.action == instinct.action
    assert restored.payload.status is InstinctStatus.ACTIVE
    assert restored.payload.evidence == instinct.evidence
    assert isinstance(restored.created_at, datetime)


def test_proposal_roundtrip_skill_payload():
    skill = Skill(name="ruff-flow", description="lint flow", body="- run ruff", source="curator")
    proposal = Proposal(kind="skill", payload=skill, rationale="graduated", confidence=0.75)
    restored = proposal_from_dict(proposal_to_dict(proposal))
    assert isinstance(restored.payload, Skill)
    assert restored.payload.name == "ruff-flow"
    assert restored.payload.status is SkillStatus.ACTIVE


def test_proposal_roundtrip_dict_payload():
    proposal = Proposal(kind="memory_edit", payload={"op": "delete"}, rationale="stale")
    restored = proposal_from_dict(proposal_to_dict(proposal))
    assert restored.payload == {"op": "delete"}


def test_session_roundtrip_preserves_messages_and_tool_calls():
    session = Session(surface="discord")
    session.add(Message(role=Role.USER, content="hi", author_id="42", name="Mal"))
    session.add(
        Message(
            role=Role.ASSISTANT,
            content="",
            tool_calls=[ToolCall(name="current_time", arguments={"tz": "utc"})],
        )
    )
    session.add(Message(role=Role.TOOL, name="current_time", content="12:00", tool_call_id="abc"))
    restored = session_from_dict(session_to_dict(session))
    assert restored.id == session.id
    assert restored.surface == "discord"
    assert len(restored.messages) == 3
    assert restored.messages[0].role is Role.USER
    assert restored.messages[0].author_id == "42"
    assert restored.messages[1].tool_calls[0].name == "current_time"
    assert restored.messages[1].tool_calls[0].arguments == {"tz": "utc"}
    assert restored.messages[2].tool_call_id == "abc"


# --- store behavior ----------------------------------------------------------


def test_inmemory_store_defaults_empty():
    store = InMemoryStateStore()
    assert store.load_traits() == []
    assert store.load_skills() == []
    assert store.load_instincts() == []
    assert store.load_pending() == []
    assert store.load_sessions() == []


def test_file_store_missing_dir_loads_empty(tmp_path):
    store = FileStateStore(tmp_path / "does-not-exist-yet")
    assert store.load_traits() == []
    assert store.load_pending() == []


def test_file_store_traits_survive_new_instance(tmp_path):
    FileStateStore(tmp_path).save_traits(["Be terse.", "No preamble."])
    assert FileStateStore(tmp_path).load_traits() == ["Be terse.", "No preamble."]


def test_file_store_skills_survive_new_instance(tmp_path):
    skill = Skill(name="s", description="d", body="b", source="curator")
    FileStateStore(tmp_path).save_skills([skill])
    restored = FileStateStore(tmp_path).load_skills()
    assert len(restored) == 1 and restored[0].name == "s" and restored[0].source == "curator"


def test_file_store_instincts_survive_new_instance(tmp_path):
    inst = Instinct(trigger="t", action="a", status=InstinctStatus.ACTIVE)
    FileStateStore(tmp_path).save_instincts([inst])
    restored = FileStateStore(tmp_path).load_instincts()
    assert len(restored) == 1 and restored[0].status is InstinctStatus.ACTIVE


def test_file_store_pending_proposals_survive_new_instance(tmp_path):
    proposal = Proposal(kind="instinct", payload=Instinct("t", "a"), rationale="r")
    FileStateStore(tmp_path).save_pending([proposal])
    restored = FileStateStore(tmp_path).load_pending()
    assert len(restored) == 1 and restored[0].id == proposal.id


def test_file_store_sessions_survive_new_instance(tmp_path):
    session = Session(surface="cli")
    session.add(Message(role=Role.USER, content="remember me"))
    FileStateStore(tmp_path).save_sessions([session])
    restored = FileStateStore(tmp_path).load_sessions()
    assert len(restored) == 1 and restored[0].messages[0].content == "remember me"


def test_file_store_write_is_atomic_no_tmp_leftovers(tmp_path):
    store = FileStateStore(tmp_path)
    store.save_traits(["a"])
    store.save_traits(["a", "b"])
    leftovers = [p for p in tmp_path.iterdir() if p.suffix != ".json"]
    assert leftovers == []
    assert store.load_traits() == ["a", "b"]


# --- factory -----------------------------------------------------------------


def test_build_state_empty_dir_gives_inmemory():
    store = build_state(Settings(state_dir=""))
    assert isinstance(store, InMemoryStateStore)


def test_build_state_dir_gives_file_store(tmp_path):
    store = build_state(Settings(state_dir=str(tmp_path)))
    assert isinstance(store, FileStateStore)


def test_default_state_dir_is_kaizen_home(monkeypatch):
    monkeypatch.delenv("KAIZEN_STATE_DIR", raising=False)
    assert Settings().state_dir == "~/.kaizen/state"
