"""Shared session store for the headless core.

Sessions live in memory (the working set) and snapshot to the
:class:`~kaizen.state.base.StateStore` after every mutation, so a daemon
restart picks the conversations back up. Every surface that talks to the
service shares this one store — that is the "one mind" property.
"""
from __future__ import annotations

import asyncio

from kaizen.core.models import Session
from kaizen.state.base import StateStore


class SessionStore:
    def __init__(self, state: StateStore) -> None:
        self._state = state
        self._sessions: dict[str, Session] = {s.id: s for s in state.load_sessions()}
        # Turn-serialization locks. Keyed by (session, event loop) because
        # asyncio primitives bind to the loop that first awaits them and the
        # test client runs each request on a fresh loop; under uvicorn there
        # is exactly one loop, so this behaves as one lock per session.
        self._locks: dict[tuple[str, int], asyncio.Lock] = {}

    def create(self, surface: str = "api") -> Session:
        session = Session(surface=surface)
        self._sessions[session.id] = session
        self.snapshot()
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def list(self) -> list[Session]:
        return list(self._sessions.values())

    def lock(self, session_id: str) -> asyncio.Lock:
        key = (session_id, id(asyncio.get_running_loop()))
        lock = self._locks.get(key)
        if lock is None:
            lock = self._locks[key] = asyncio.Lock()
        return lock

    def snapshot(self) -> None:
        self._state.save_sessions(list(self._sessions.values()))
