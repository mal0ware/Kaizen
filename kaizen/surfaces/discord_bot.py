"""Discord surface — a thin client that connects Discord to the Kaizen engine.

Run with: ``python -m kaizen.surfaces.discord_bot`` (needs KAIZEN_DISCORD_TOKEN).

Two modes, chosen at connect time like the CLI:

- **Client mode** — if the headless daemon answers at ``KAIZEN_SERVICE_URL``,
  every turn goes over HTTP to the shared brain (one session per channel,
  stored service-side), so Discord and the CLI literally share context.
- **Embedded mode** — no daemon: builds the engine in-process via
  ``build_agent``, exactly as before.

Carries the Discord user id (snowflake) as ``author_id`` (the identity
anchor, ADR 0003).

Triggering (ADR 0005): DMs always; servers when @mentioned, when you reply to
one of its messages, or — during a short per-user "active conversation"
window — when the interjection governor judges the message relevant enough.

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
from collections import deque

import discord

from kaizen.bootstrap import AgentBundle, build_agent
from kaizen.config import load_settings
from kaizen.core.models import Message, Role, Session
from kaizen.curator.apply import apply_approval
from kaizen.realtime.governor import GovernorConfig, InterjectionGovernor
from kaizen.service.client import ServiceClient, connect
from kaizen.surfaces.engagement import EngagementContext, should_engage


def _chunks(text: str, limit: int = 1900) -> list[str]:
    text = text or "(no response)"
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def _format_proposals(bundle: AgentBundle) -> str:
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


def _handle_dm_command(content: str, bundle: AgentBundle) -> str | None:
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


async def handle_dm_command_remote(content: str, remote: ServiceClient) -> str | None:
    """Client-mode twin of ``_handle_dm_command`` — same commands, over HTTP."""
    cmd, _, arg = content.strip().partition(" ")
    if cmd == "!proposals":
        pending = await remote.proposals()
        if not pending:
            return "(no pending proposals)"
        return "\n".join(
            f"`{p['id'][:8]}` **{p['kind']}** conf={p['confidence']:.2f} — {p['summary']}\n"
            f"    _why:_ {p['rationale']}"
            for p in pending
        )
    if cmd in {"!approve", "!reject"}:
        if not arg.strip():
            return f"usage: `{cmd} <id-prefix>`"
        match = next(
            (p for p in await remote.proposals() if p["id"].startswith(arg.strip())),
            None,
        )
        if match is None:
            return f"no pending proposal matches `{arg.strip()}`"
        if cmd == "!approve":
            return str((await remote.approve(match["id"]))["note"])
        await remote.reject(match["id"])
        return f"rejected `{match['id'][:8]}`"
    if cmd == "!traits":
        traits = await remote.traits()
        if not traits:
            return "(no learned traits yet — approve an instinct to add one)"
        return "\n".join(f"- {t}" for t in traits)
    if cmd == "!skills":
        skills = await remote.skills()
        return "\n".join(f"- **{s['name']}**: {s['description']}" for s in skills)
    return None


async def remote_turn(
    remote: ServiceClient,
    session_ids: dict[int, str],
    channel_id: int,
    content: str,
    author_id: str,
    author_name: str | None,
) -> str:
    """One user turn through the daemon: ensure a service session for this
    channel, post the message, return the reply text."""
    session_id = session_ids.get(channel_id)
    if session_id is None:
        session = await remote.create_session(surface="discord")
        session_id = session_ids[channel_id] = session["id"]
    reply = await remote.send(session_id, content, author_id=author_id, name=author_name)
    return str(reply["content"])


def run(service_url: str | None = None) -> None:
    settings = load_settings()
    if not settings.discord_token:
        raise SystemExit(
            "Set KAIZEN_DISCORD_TOKEN in your .env "
            "(Discord Developer Portal -> your app -> Bot -> Token)."
        )
    url = service_url if service_url is not None else settings.service_url

    # Filled in during on_ready: exactly one of the two is set.
    bundle: AgentBundle | None = None
    remote: ServiceClient | None = None

    sessions: dict[int, Session] = {}  # embedded mode: channel id -> Session
    session_ids: dict[int, str] = {}  # client mode: channel id -> service session id
    active: dict[tuple[int, int], float] = {}  # (channel_id, user_id) -> window expiry
    # Rolling per-channel context for the interjection governor (ADR 0005):
    # every message the bot can see, engaged with or not, bounded per channel.
    recent_by_channel: dict[int, deque[Message]] = {}
    governor = InterjectionGovernor(GovernorConfig(talkativeness=settings.talkativeness))

    intents = discord.Intents.default()
    intents.message_content = True  # privileged intent — enable it in the Developer Portal
    client = discord.Client(intents=intents)

    def _is_reply_to_bot(message: discord.Message) -> bool:
        ref = message.reference
        resolved = getattr(ref, "resolved", None) if ref is not None else None
        return resolved is not None and getattr(resolved, "author", None) == client.user

    @client.event
    async def on_ready():
        nonlocal bundle, remote
        remote = await connect(url)
        if remote is not None:
            print(f"Kaizen online as {client.user} (client mode, daemon at {url})")
            return
        bundle = build_agent(settings)
        memory = bundle.loop.context.memory
        init = getattr(memory, "init_db", None)
        if init is not None:
            await init()
        print(
            f"Kaizen online as {client.user} "
            f"(embedded mode — no daemon at {url}; memory: {memory.name})"
        )

    @client.event
    async def on_message(message: discord.Message):
        if message.author == client.user or message.author.bot:
            return
        if bundle is None and remote is None:
            return  # still connecting

        is_dm = message.guild is None
        mentioned = client.user in message.mentions
        key = (message.channel.id, message.author.id)
        now = time.monotonic()
        in_active_window = active.get(key, 0.0) > now

        recent = recent_by_channel.setdefault(message.channel.id, deque(maxlen=10))
        incoming = Message(
            role=Role.USER,
            content=message.content,
            author_id=str(message.author.id),
            name=message.author.display_name,
        )
        ctx = EngagementContext(
            is_dm=is_dm,
            mentioned=mentioned,
            is_reply_to_bot=_is_reply_to_bot(message),
            in_active_window=in_active_window,
        )
        engage = should_engage(ctx, incoming, list(recent), governor)
        recent.append(incoming)
        if not engage:
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
            if remote is not None:
                reply_text = await handle_dm_command_remote(content, remote)
            else:
                assert bundle is not None
                reply_text = _handle_dm_command(content, bundle)
            if reply_text is not None:
                for chunk in _chunks(reply_text):
                    await message.channel.send(chunk)
                return

        try:
            async with message.channel.typing():
                if remote is not None:
                    text = await remote_turn(
                        remote,
                        session_ids,
                        message.channel.id,
                        content,
                        str(message.author.id),
                        message.author.display_name,
                    )
                else:
                    assert bundle is not None
                    session = sessions.setdefault(
                        message.channel.id, Session(surface="discord")
                    )
                    reply = await bundle.loop.handle(
                        session,
                        Message(
                            role=Role.USER,
                            content=content,
                            author_id=str(message.author.id),
                            name=message.author.display_name,
                        ),
                    )
                    text = reply.content
            for chunk in _chunks(text):
                await message.channel.send(chunk)
            active[key] = now + settings.active_window_seconds
        except Exception as exc:  # noqa: BLE001 — surface errors, don't crash the bot
            await message.channel.send(f"[error] {type(exc).__name__}: {str(exc)[:300]}")

    client.run(settings.discord_token)


if __name__ == "__main__":
    run()
