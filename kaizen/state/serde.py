"""Dict <-> dataclass converters for everything the state store persists.

Hand-rolled (no pydantic dependency on the core dataclasses) so the domain
models stay plain. Datetimes serialize as ISO-8601 strings. Proposal payloads
are typed by ``kind``: "instinct" -> :class:`Instinct`, "skill" ->
:class:`Skill`, anything else stays a plain dict.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from kaizen.core.models import Message, Role, Session, ToolCall
from kaizen.curator.instinct import Instinct, InstinctStatus
from kaizen.curator.proposals import Proposal, ProposalStatus
from kaizen.skills.base import Skill, SkillStatus


def _dt(value: datetime) -> str:
    return value.isoformat()


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


# --- Skill -------------------------------------------------------------------


def skill_to_dict(skill: Skill) -> dict[str, Any]:
    return {
        "name": skill.name,
        "description": skill.description,
        "body": skill.body,
        "source": skill.source,
        "status": skill.status.value,
        "created_at": _dt(skill.created_at),
        "last_used_at": _dt(skill.last_used_at) if skill.last_used_at else None,
    }


def skill_from_dict(data: dict[str, Any]) -> Skill:
    return Skill(
        name=data["name"],
        description=data["description"],
        body=data["body"],
        source=data.get("source", "authored"),
        status=SkillStatus(data.get("status", "active")),
        created_at=_parse_dt(data["created_at"]),
        last_used_at=_parse_dt(data["last_used_at"]) if data.get("last_used_at") else None,
    )


# --- Instinct ----------------------------------------------------------------


def instinct_to_dict(instinct: Instinct) -> dict[str, Any]:
    return {
        "trigger": instinct.trigger,
        "action": instinct.action,
        "confidence": instinct.confidence,
        "source": instinct.source,
        "status": instinct.status.value,
        "evidence": list(instinct.evidence),
        "first_seen": _dt(instinct.first_seen),
        "last_seen": _dt(instinct.last_seen),
    }


def instinct_from_dict(data: dict[str, Any]) -> Instinct:
    return Instinct(
        trigger=data["trigger"],
        action=data["action"],
        confidence=data.get("confidence", 0.5),
        source=data.get("source", "session"),
        status=InstinctStatus(data.get("status", "pending")),
        evidence=list(data.get("evidence", [])),
        first_seen=_parse_dt(data["first_seen"]),
        last_seen=_parse_dt(data["last_seen"]),
    )


# --- Proposal ----------------------------------------------------------------


def proposal_to_dict(proposal: Proposal) -> dict[str, Any]:
    payload: Any = proposal.payload
    if isinstance(payload, Instinct):
        payload = instinct_to_dict(payload)
    elif isinstance(payload, Skill):
        payload = skill_to_dict(payload)
    return {
        "id": proposal.id,
        "kind": proposal.kind,
        "payload": payload,
        "rationale": proposal.rationale,
        "confidence": proposal.confidence,
        "status": proposal.status.value,
        "created_at": _dt(proposal.created_at),
    }


def proposal_from_dict(data: dict[str, Any]) -> Proposal:
    kind = data["kind"]
    payload: Any = data["payload"]
    if kind == "instinct" and isinstance(payload, dict):
        payload = instinct_from_dict(payload)
    elif kind == "skill" and isinstance(payload, dict):
        payload = skill_from_dict(payload)
    return Proposal(
        kind=kind,
        payload=payload,
        rationale=data["rationale"],
        confidence=data.get("confidence", 0.5),
        status=ProposalStatus(data.get("status", "pending")),
        id=data["id"],
        created_at=_parse_dt(data["created_at"]),
    )


# --- Session -----------------------------------------------------------------


def _tool_call_to_dict(call: ToolCall) -> dict[str, Any]:
    return {"name": call.name, "arguments": call.arguments, "id": call.id}


def _message_to_dict(message: Message) -> dict[str, Any]:
    return {
        "role": message.role.value,
        "content": message.content,
        "author_id": message.author_id,
        "name": message.name,
        "tool_calls": [_tool_call_to_dict(c) for c in message.tool_calls],
        "tool_call_id": message.tool_call_id,
        "created_at": _dt(message.created_at),
    }


def _message_from_dict(data: dict[str, Any]) -> Message:
    return Message(
        role=Role(data["role"]),
        content=data.get("content", ""),
        author_id=data.get("author_id"),
        name=data.get("name"),
        tool_calls=[
            ToolCall(name=c["name"], arguments=c.get("arguments", {}), id=c["id"])
            for c in data.get("tool_calls", [])
        ],
        tool_call_id=data.get("tool_call_id"),
        created_at=_parse_dt(data["created_at"]),
    )


def session_to_dict(session: Session) -> dict[str, Any]:
    return {
        "id": session.id,
        "surface": session.surface,
        "messages": [_message_to_dict(m) for m in session.messages],
        "created_at": _dt(session.created_at),
    }


def session_from_dict(data: dict[str, Any]) -> Session:
    return Session(
        id=data["id"],
        surface=data.get("surface", "cli"),
        messages=[_message_from_dict(m) for m in data.get("messages", [])],
        created_at=_parse_dt(data["created_at"]),
    )
