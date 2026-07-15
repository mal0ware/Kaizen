"""Wire models for the headless-core API.

Pydantic here (the API boundary) only — the domain stays plain dataclasses.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SessionCreate(BaseModel):
    surface: str = "api"


class MessageIn(BaseModel):
    content: str
    author_id: str | None = None
    name: str | None = None


class MessageOut(BaseModel):
    role: str
    content: str
    name: str | None = None
    created_at: datetime


class SessionOut(BaseModel):
    id: str
    surface: str
    created_at: datetime
    messages: list[MessageOut]


class ProposalOut(BaseModel):
    id: str
    kind: str
    status: str
    confidence: float
    rationale: str
    summary: str


class DecisionOut(BaseModel):
    id: str
    status: str
    note: str


class TraitsOut(BaseModel):
    traits: list[str]


class SkillOut(BaseModel):
    name: str
    description: str


class HealthOut(BaseModel):
    status: str
    brains: dict[str, str]
    memory: str
    skills: int
    pending_proposals: int
