"""Discord surface — a thin client that connects Discord to the Kaizen engine.

Run with: `python -m kaizen.surfaces.discord_bot` (needs KAIZEN_DISCORD_TOKEN).

Reuses the same engine wiring as the CLI (providers + memory + scribe), keeps
one Session per channel, and carries the Discord user id (snowflake) as author_id
(the identity anchor, ADR 0003).

Triggering (v1.5 — a step toward the interjection governor, ADR 0005):
  - DMs: always.
  - Servers: when @mentioned, when you reply to one of its messages, or while a
    short per-user "active conversation" window is open (ping once, then talk).

`discord.py` is an optional dep (`pip install discord.py`).
"""
from __future__ import annotations

import time

import discord

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


def _build_loop(settings):
    memory = build_memory(settings, InMemoryStore())
    tools = ToolRegistry()
    tools.register(CurrentTimeTool())
    tools.register(EchoTool())
    router = build_router(settings, MockProvider())
    scribe = Scribe(router.providers[Tier.LOCAL], memory) if settings.enable_scribe else None
    context = ContextEngine(memory, system_prompt=settings.system_prompt)
    return AgentLoop(router, context, tools, scribe=scribe), memory


def _chunks(text: str, limit: int = 1900) -> list[str]:
    text = text or "(no response)"
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def run() -> None:
    settings = load_settings()
    if not settings.discord_token:
        raise SystemExit(
            "Set KAIZEN_DISCORD_TOKEN in your .env "
            "(Discord Developer Portal -> your app -> Bot -> Token)."
        )

    agent, memory = _build_loop(settings)
    sessions: dict[int, Session] = {}
    active: dict[tuple[int, int], float] = {}  # (channel_id, user_id) -> window expiry

    intents = discord.Intents.default()
    intents.message_content = True  # privileged intent — enable it in the Developer Portal
    client = discord.Client(intents=intents)

    def _is_reply_to_bot(message: discord.Message) -> bool:
        ref = message.reference
        resolved = getattr(ref, "resolved", None) if ref is not None else None
        return resolved is not None and getattr(resolved, "author", None) == client.user

    @client.event
    async def on_ready():
        init = getattr(memory, "init_db", None)
        if init is not None:
            await init()
        print(f"Kaizen online as {client.user} (memory: {memory.name})")

    @client.event
    async def on_message(message: discord.Message):
        if message.author == client.user or message.author.bot:
            return

        is_dm = message.guild is None
        mentioned = client.user in message.mentions
        key = (message.channel.id, message.author.id)
        now = time.monotonic()
        in_active_window = active.get(key, 0.0) > now

        if not (is_dm or mentioned or _is_reply_to_bot(message) or in_active_window):
            return

        content = message.content
        if mentioned and client.user is not None:
            content = (
                content.replace(f"<@{client.user.id}>", "")
                .replace(f"<@!{client.user.id}>", "")
                .strip()
            )
        if not content:
            return

        session = sessions.setdefault(message.channel.id, Session(surface="discord"))
        try:
            async with message.channel.typing():
                reply = await agent.handle(
                    session,
                    Message(
                        role=Role.USER,
                        content=content,
                        author_id=str(message.author.id),
                        name=message.author.display_name,
                    ),
                )
            for chunk in _chunks(reply.content):
                await message.channel.send(chunk)
            active[key] = now + settings.active_window_seconds
        except Exception as exc:  # noqa: BLE001 — surface errors, don't crash the bot
            await message.channel.send(f"⚠️ {type(exc).__name__}: {str(exc)[:300]}")

    client.run(settings.discord_token)


if __name__ == "__main__":
    run()
