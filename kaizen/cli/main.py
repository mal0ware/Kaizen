"""Runnable mock CLI: `python -m kaizen`.

Builds an AgentLoop wired entirely with mocks/in-memory parts — no infra, no
keys. Real providers/stores swap in behind the same interfaces later.
"""
from __future__ import annotations

import asyncio

from kaizen.config import load_settings
from kaizen.core.context import ContextEngine
from kaizen.core.loop import AgentLoop
from kaizen.core.models import Message, Role, Session
from kaizen.memory.inmemory import InMemoryStore
from kaizen.orchestration.router import Router
from kaizen.providers.base import Tier
from kaizen.providers.mock import MockProvider
from kaizen.tools.base import ToolRegistry
from kaizen.tools.builtin import CurrentTimeTool, EchoTool


def build_agent() -> tuple[AgentLoop, Session]:
    settings = load_settings()

    memory = InMemoryStore()
    tools = ToolRegistry()
    tools.register(CurrentTimeTool())
    tools.register(EchoTool())

    # Dev wiring: one mock provider serves every tier (no infra / no keys).
    mock = MockProvider()
    router = Router({Tier.LOCAL: mock, Tier.CHEAP: mock, Tier.FRONTIER: mock})
    context = ContextEngine(memory, system_prompt=settings.system_prompt)

    return AgentLoop(router, context, tools), Session(surface="cli")


async def _chat() -> None:
    agent, session = build_agent()
    print("Kaizen (mock dev CLI). Type 'exit' to quit.\n")
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
