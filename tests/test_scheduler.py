"""Background-cognition scheduler tests. Fake sleeps only — no real waiting."""
from __future__ import annotations

import asyncio

from kaizen.bootstrap import build_agent
from kaizen.config import Settings
from kaizen.core.models import Message, Role, Session
from kaizen.curator.instinct import Instinct, InstinctStatus
from kaizen.service.scheduler import Scheduler
from kaizen.service.sessions import SessionStore
from kaizen.providers.base import CompletionRequest, CompletionResponse, Tier


class _FactProvider:
    """Stub provider whose completions are fact-extraction JSON."""

    name = "fact-stub"
    tier = Tier.LOCAL

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            text='[{"subject":"user","attribute":"project","value":"Hermes"}]',
            model="fact-stub",
        )


def _fixture() -> tuple:
    bundle = build_agent(Settings())
    sessions = SessionStore(bundle.state)
    return bundle, sessions


async def test_curator_pass_reviews_sessions_into_proposals():
    bundle, sessions = _fixture()
    session = sessions.create(surface="cli")
    for _ in range(3):
        session.add(Message(role=Role.USER, content="I prefer terse replies, no preamble"))

    scheduler = Scheduler(bundle, sessions)
    await scheduler.curator_pass()
    assert any(p.kind == "instinct" for p in bundle.queue.pending())


async def test_curator_pass_graduates_active_instincts_into_skill_proposals():
    """The gap this scheduler closes: curator.evolve finally runs at runtime."""
    bundle, sessions = _fixture()
    bundle.instincts.extend(
        [
            Instinct(trigger="ruff lint python", action="run ruff before committing",
                     status=InstinctStatus.ACTIVE, confidence=0.7),
            Instinct(trigger="ruff format python", action="format python with ruff",
                     status=InstinctStatus.ACTIVE, confidence=0.8),
        ]
    )
    scheduler = Scheduler(bundle, sessions)
    await scheduler.curator_pass()
    skills = [p for p in bundle.queue.pending() if p.kind == "skill"]
    assert skills, "expected evolve() to graduate a skill proposal"
    assert "ruff" in (skills[0].payload.name + skills[0].payload.description)


async def test_curator_pass_is_idempotent_across_runs():
    bundle, sessions = _fixture()
    session = sessions.create(surface="cli")
    for _ in range(3):
        session.add(Message(role=Role.USER, content="I prefer terse replies, no preamble"))
    scheduler = Scheduler(bundle, sessions)
    await scheduler.curator_pass()
    count = len(bundle.queue.pending())
    await scheduler.curator_pass()
    assert len(bundle.queue.pending()) == count  # fingerprint dedup holds


async def test_scribe_pass_consolidates_sessions_into_memory():
    bundle, sessions = _fixture()
    bundle.loop.scribe.provider = _FactProvider()  # type: ignore[union-attr]
    session = sessions.create(surface="discord")
    session.add(Message(role=Role.USER, content="I'm building Hermes"))

    scheduler = Scheduler(bundle, sessions)
    await scheduler.scribe_pass()
    facts = await bundle.loop.context.memory.search("Hermes", k=5)
    assert any(f.value == "Hermes" for f in facts)


async def test_periodic_loop_uses_injected_sleep_no_real_waiting():
    bundle, sessions = _fixture()
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) >= 3:
            raise asyncio.CancelledError

    runs = 0

    async def tick() -> None:
        nonlocal runs
        runs += 1

    scheduler = Scheduler(bundle, sessions, sleep=fake_sleep)
    try:
        await scheduler._periodic(60, tick)
    except asyncio.CancelledError:
        pass
    assert sleeps == [60, 60, 60]
    assert runs == 2  # third sleep cancelled before the third tick


async def test_periodic_swallows_pass_errors():
    bundle, sessions = _fixture()
    calls = 0

    async def fake_sleep(seconds: float) -> None:
        nonlocal calls
        calls += 1
        if calls >= 3:
            raise asyncio.CancelledError

    async def bad_tick() -> None:
        raise RuntimeError("cognition hiccup")

    scheduler = Scheduler(bundle, sessions, sleep=fake_sleep)
    try:
        await scheduler._periodic(1, bad_tick)
    except asyncio.CancelledError:
        pass
    assert calls == 3  # kept looping despite the failing pass


async def test_start_respects_disabled_cadences():
    bundle, sessions = _fixture()
    scheduler = Scheduler(bundle, sessions, scribe_interval=0, curator_interval=0)
    scheduler.start()
    assert scheduler.tasks == []
    await scheduler.stop()


async def test_start_and_stop_cancel_cleanly():
    bundle, sessions = _fixture()
    scheduler = Scheduler(bundle, sessions, scribe_interval=3600, curator_interval=3600)
    scheduler.start()
    assert len(scheduler.tasks) == 2
    await scheduler.stop()
    assert all(t.done() for t in scheduler.tasks) or scheduler.tasks == []


def test_session_deserialization_note():
    """Guard: SessionStore.list() hands real Session objects to the passes."""
    bundle, sessions = _fixture()
    created = sessions.create()
    assert isinstance(sessions.list()[0], Session)
    assert sessions.get(created.id) is created
