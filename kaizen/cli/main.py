"""Runnable dev CLI: `python -m kaizen`.

Wires the core via `build_router` + `build_memory` (+ the scribe), so it uses
real providers, real Postgres, and ambient learning when configured, and falls
back to mock + in-memory when nothing is set up — it always runs, infra or not.
"""
from __future__ import annotations

import asyncio

from kaizen.config import load_settings
from kaizen.core.context import ContextEngine
from kaizen.core.loop import AgentLoop
from kaizen.core.models import Message, Role, Session
from kaizen.memory.factory import build_memory
from kaizen.memory.inmemory import InMemoryStore
from kaizen.memory.scribe import Scribe
from kaizen.providers.base import Tier
from kaizen.providers.factory import build_router
from kaizen.providers.mock import MockProvider
from kaizen.tools.base import ToolRegistry
from kaizen.tools.builtin import CurrentTimeTool, EchoTool


def build_agent() -> tuple[AgentLoop, Session]:
    settings = load_settings()

    memory = build_memory(settings, InMemoryStore())
    tools = ToolRegistry()
    tools.register(CurrentTimeTool())
    tools.register(EchoTool())

    router = build_router(settings, MockProvider())
    scribe = Scribe(router.providers[Tier.LOCAL], memory) if settings.enable_scribe else None
    context = ContextEngine(memory, system_prompt=settings.system_prompt)

    return AgentLoop(router, context, tools, scribe=scribe), Session(surface="cli")


async def _maybe_init(memory: object) -> None:
    init = getattr(memory, "init_db", None)
    if init is not None:
        await init()


async def _chat() -> None:
    agent, session = build_agent()
    await _maybe_init(agent.context.memory)

    brains = ", ".join(
        f"{tier.name.lower()}={provider.name}"
        for tier, provider in sorted(agent.router.providers.items(), key=lambda kv: kv[0].value)
    )
    learns = "on" if agent.scribe is not None else "off"
    print(
        f"Kaizen dev CLI — brains: {brains}, memory: {agent.context.memory.name}, "
        f"learning: {learns}. Type 'exit' to quit.\n"
    )

    loop = asyncio.get_event_loop()
    while True:
        try:
            user = await loop.run_in_executor(None, input, "you> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user.strip().lower() in {"exit", "quit"}:
            break
        reply = await agent.handle(
            session, Message(role=Role.USER, content=user, author_id="local")
        )
        print(f"kaizen> {reply.content}\n")


def run() -> None:
    asyncio.run(_chat())


if __name__ == "__main__":
    run()
