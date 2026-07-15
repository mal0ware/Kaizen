"""Discord surface — a thin client that connects Discord to the Kaizen engine.

Run with: ``python -m kaizen.surfaces.discord_bot`` (needs KAIZEN_DISCORD_TOKEN).

Reuses the same engine wiring as the CLI (``build_agent`` returns an
:class:`AgentBundle` with the loop, gate, queue, skills, and learned traits),
keeps one Session per channel, and carries the Discord user id (snowflake) as
``author_id`` (the identity anchor, ADR 0003).

Triggering (v1.5 — a step toward the interjection governor, ADR 0005):
  - DMs: always.
  - Servers: when @mentioned, when you reply to one of its messages, or while
    a short per-user "active conversation" window is open (ping once, then talk).

Operator-only commands (DM the bot):
    !proposals          list pending curator proposals
    !approve <id>       approve a proposal (id prefix is fine)
    !reject  <id>       reject a proposal
    !traits             show learned-voice traits
    !skills             show active skills

``discord.py`` is an optional dep (``pip install discord.py``).
"""
from __future__ import annotations

import time

import discord

from kaizen.bootstrap import build_agent
from kaizen.config import load_settings
from kaizen.core.models import Message, Role, Session
from kaizen.curator.apply import apply_approval


def _chunks(text: str, limit: int = 1900) -> list[str]:
    text = text or "(no response)"
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def _format_proposals(bundle) -> str:
    pending = bundle.queue.pending()
    if not pending:
        return "(no pending proposals)"
    lines = []
    for p in pending:
        payload = getattr(p.payload, "action", None) or getattr(p.payload, "name", "")
        lines.append(
            f"`{p.id[:8]}` **{p.kind}** conf={p.confidence:.2f} — {payload}\n"
            f"    _why:_ {p.rationale}"
        )
    return "\n".join(lines)


def _handle_dm_command(content: str, bundle) -> str | None:
    """Return a reply string if ``content`` is a recognized command, else None."""
    cmd, _, arg = content.strip().partition(" ")
    if cmd == "!proposals":
        return _format_proposals(bundle)
    if cmd in {"!approve", "!reject"}:
        if not arg.strip():
            return f"usage: `{cmd} <id-prefix>`"
        match = next(
            (p for p in bundle.queue.pending() if p.id.startswith(arg.strip())),
            None,
        )
        if match is None:
            return f"no pending proposal matches `{arg.strip()}`"
        if cmd == "!approve":
            bundle.queue.approve(match.id)
            return apply_approval(
                match,
                bundle.learned_traits,
                bundle.skills,
                state=bundle.state,
                instincts=bundle.instincts,
            )
        bundle.queue.reject(match.id)
        return f"rejected `{match.id[:8]}`"
    if cmd == "!traits":
        if not bundle.learned_traits:
            return "(no learned traits yet — approve an instinct to add one)"
        return "\n".join(f"- {t}" for t in bundle.learned_traits)
    if cmd == "!skills":
        return "\n".join(f"- **{s['name']}**: {s['description']}" for s in bundle.skills.specs())
    return None


def run() -> None:
    settings = load_settings()
    if not settings.discord_token:
        raise SystemExit(
            "Set KAIZEN_DISCORD_TOKEN in your .env "
            "(Discord Developer Portal -> your app -> Bot -> Token)."
        )

    bundle = build_agent(settings)
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
        memory = bundle.loop.context.memory
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

        # Operator commands are DM-only — keeps gate access scoped to private chat.
        if is_dm and content.startswith("!"):
            reply_text = _handle_dm_command(content, bundle)
            if reply_text is not None:
                for chunk in _chunks(reply_text):
                    await message.channel.send(chunk)
                return

        session = sessions.setdefault(message.channel.id, Session(surface="discord"))
        try:
            async with message.channel.typing():
                reply = await bundle.loop.handle(
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
