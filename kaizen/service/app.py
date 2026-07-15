"""The headless core: ONE agent behind an ASGI app (the "one mind").

Surfaces (CLI, Discord, anything speaking HTTP) are thin clients against this
API. The service owns the single :class:`~kaizen.bootstrap.AgentBundle`, the
shared :class:`~kaizen.service.sessions.SessionStore`, and — via the state
store — everything that must survive a restart.

Post-turn cognition runs inline here (``background_cognition=False``): every
reply returns with its scribe/curator pass already applied and snapshotted,
which also makes the API deterministic under test.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException

from kaizen.bootstrap import AgentBundle, build_agent
from kaizen.config import Settings, load_settings
from kaizen.core.models import Message, Role, Session
from kaizen.curator.apply import apply_approval
from kaizen.curator.proposals import Proposal
from kaizen.service.schemas import (
    DecisionOut,
    HealthOut,
    MessageIn,
    MessageOut,
    ProposalOut,
    SessionCreate,
    SessionOut,
    SkillOut,
    TraitsOut,
)
from kaizen.service.scheduler import Scheduler
from kaizen.service.sessions import SessionStore


def _message_out(message: Message) -> MessageOut:
    return MessageOut(
        role=message.role.value,
        content=message.content,
        name=message.name,
        created_at=message.created_at,
    )


def _session_out(session: Session) -> SessionOut:
    return SessionOut(
        id=session.id,
        surface=session.surface,
        created_at=session.created_at,
        messages=[_message_out(m) for m in session.messages],
    )


def _proposal_out(proposal: Proposal) -> ProposalOut:
    summary = getattr(proposal.payload, "action", None) or getattr(proposal.payload, "name", "")
    return ProposalOut(
        id=proposal.id,
        kind=proposal.kind,
        status=proposal.status.value,
        confidence=proposal.confidence,
        rationale=proposal.rationale,
        summary=str(summary),
    )


def create_app(
    bundle: AgentBundle | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    bundle = bundle or build_agent(settings)
    # The service awaits post-turn cognition so replies return fully learned
    # and the session snapshot below is never behind.
    bundle.loop.background_cognition = False
    sessions = SessionStore(bundle.state)
    scheduler = Scheduler(
        bundle,
        sessions,
        scribe_interval=settings.scribe_interval_seconds,
        curator_interval=settings.curator_interval_seconds,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init = getattr(bundle.loop.context.memory, "init_db", None)
        if init is not None:
            await init()
        scheduler.start()
        try:
            yield
        finally:
            await scheduler.stop()

    app = FastAPI(title="kaizen", lifespan=lifespan)
    app.state.bundle = bundle
    app.state.sessions = sessions
    app.state.scheduler = scheduler

    def _get_session(session_id: str) -> Session:
        session = sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"unknown session: {session_id}")
        return session

    @app.get("/health", response_model=HealthOut)
    async def health() -> HealthOut:
        return HealthOut(
            status="ok",
            brains={
                tier.name.lower(): provider.name
                for tier, provider in bundle.loop.router.providers.items()
            },
            memory=bundle.loop.context.memory.name,
            skills=len(bundle.skills.list()),
            pending_proposals=len(bundle.queue.pending()),
        )

    @app.post("/sessions", response_model=SessionOut, status_code=201)
    async def create_session(body: SessionCreate) -> SessionOut:
        return _session_out(sessions.create(surface=body.surface))

    @app.get("/sessions/{session_id}", response_model=SessionOut)
    async def get_session(session_id: str) -> SessionOut:
        return _session_out(_get_session(session_id))

    @app.post("/sessions/{session_id}/messages", response_model=MessageOut)
    async def post_message(session_id: str, body: MessageIn) -> MessageOut:
        session = _get_session(session_id)
        message = Message(
            role=Role.USER, content=body.content, author_id=body.author_id, name=body.name
        )
        async with sessions.lock(session_id):
            reply = await bundle.loop.handle(session, message)
            sessions.snapshot()
        return _message_out(reply)

    @app.get("/proposals", response_model=list[ProposalOut])
    async def list_proposals() -> list[ProposalOut]:
        return [_proposal_out(p) for p in bundle.queue.pending()]

    def _decide(proposal_id: str, approve: bool) -> DecisionOut:
        proposal = bundle.queue.get(proposal_id) or bundle.gate.get(proposal_id)
        if proposal is None:
            raise HTTPException(status_code=404, detail=f"unknown proposal: {proposal_id}")
        try:
            if approve:
                bundle.queue.approve(proposal_id)
                note = apply_approval(
                    proposal,
                    bundle.learned_traits,
                    bundle.skills,
                    state=bundle.state,
                    instincts=bundle.instincts,
                )
            else:
                bundle.queue.reject(proposal_id)
                note = f"rejected {proposal_id[:8]}"
        except ValueError as exc:  # already decided
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return DecisionOut(id=proposal_id, status=proposal.status.value, note=note)

    @app.post("/proposals/{proposal_id}/approve", response_model=DecisionOut)
    async def approve_proposal(proposal_id: str) -> DecisionOut:
        return _decide(proposal_id, approve=True)

    @app.post("/proposals/{proposal_id}/reject", response_model=DecisionOut)
    async def reject_proposal(proposal_id: str) -> DecisionOut:
        return _decide(proposal_id, approve=False)

    @app.get("/traits", response_model=TraitsOut)
    async def traits() -> TraitsOut:
        return TraitsOut(traits=list(bundle.learned_traits))

    @app.get("/skills", response_model=list[SkillOut])
    async def skills() -> list[SkillOut]:
        return [SkillOut(name=s["name"], description=s["description"])
                for s in bundle.skills.specs()]

    return app
