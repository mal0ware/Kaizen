"""Background cognition — the "always learning" half of the daemon.

Two cadences, both asyncio tasks owned by the service lifespan:

- **scribe pass**: re-observe every live session, catching anything the
  per-turn pass missed (the scribe's watermark makes this idempotent).
- **curator pass**: review every live session for new instinct proposals,
  then run ``curator.evolve`` over the *approved* (ACTIVE) instincts so
  related learnings graduate into skill proposals — the step that never ran
  at runtime before this scheduler existed. Everything still lands in the
  proposal queue behind the approval gate; the scheduler proposes, it never
  applies.

``sleep`` is injectable so tests drive the loop with a fake clock.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from kaizen.bootstrap import AgentBundle
from kaizen.service.sessions import SessionStore

SleepFn = Callable[[float], Awaitable[None]]


class Scheduler:
    def __init__(
        self,
        bundle: AgentBundle,
        sessions: SessionStore,
        scribe_interval: float = 300.0,
        curator_interval: float = 600.0,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self.bundle = bundle
        self.sessions = sessions
        self.scribe_interval = scribe_interval
        self.curator_interval = curator_interval
        self._sleep = sleep
        self.tasks: list[asyncio.Task[None]] = []

    # --- passes ----------------------------------------------------------------

    async def scribe_pass(self) -> None:
        """Consolidate every live session into memory. Scribe.observe swallows
        its own errors and skips sessions with nothing new."""
        scribe = self.bundle.loop.scribe
        if scribe is None:
            return
        for session in self.sessions.list():
            await scribe.observe(session)

    async def curator_pass(self) -> None:
        """Review sessions for instincts, then graduate ACTIVE instincts into
        skill proposals. The queue's fingerprint dedup keeps this idempotent."""
        curator = self.bundle.loop.curator
        queue = self.bundle.loop.proposal_queue
        if curator is None or queue is None:
            return
        for session in self.sessions.list():
            try:
                for proposal in await curator.review(session):
                    queue.add(proposal)
            except Exception:
                continue
        for proposal in curator.evolve(self.bundle.instincts):
            queue.add(proposal)

    # --- cadence ----------------------------------------------------------------

    async def _periodic(self, interval: float, fn: Callable[[], Awaitable[None]]) -> None:
        """Sleep-then-run forever. A failing pass is logged by omission (the
        passes guard themselves); cancellation propagates for clean shutdown."""
        while True:
            await self._sleep(interval)
            try:
                await fn()
            except asyncio.CancelledError:
                raise
            except Exception:
                continue

    def start(self) -> None:
        """Spawn one task per enabled cadence (interval <= 0 disables)."""
        if self.scribe_interval > 0:
            self.tasks.append(
                asyncio.create_task(self._periodic(self.scribe_interval, self.scribe_pass))
            )
        if self.curator_interval > 0:
            self.tasks.append(
                asyncio.create_task(self._periodic(self.curator_interval, self.curator_pass))
            )

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        for task in self.tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
