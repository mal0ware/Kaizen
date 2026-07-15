"""Runnable CLI: ``python -m kaizen`` (REPL) and ``python -m kaizen serve``.

Two modes, chosen automatically at startup:

- **Client mode** — if a daemon answers at ``KAIZEN_SERVICE_URL`` (default
  ``http://127.0.0.1:8420``), the REPL is a thin HTTP client against the
  shared brain. Start the daemon with ``python -m kaizen serve``.
- **Embedded mode** — no daemon reachable: builds the full agent in-process
  (mock + in-memory fallbacks, like always) and says so in one line.

In-session commands (both modes):
    /proposals          list pending curator proposals
    /approve <id>       approve a proposal (id prefix is fine)
    /reject  <id>       reject a proposal
    /traits             show the active learned-voice traits
    /skills             show the active skills
    /help               this list
    exit | quit         leave
"""
from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

from kaizen.bootstrap import AgentBundle, build_agent
from kaizen.config import load_settings
from kaizen.core.models import Message, Role
from kaizen.curator.apply import apply_approval

if TYPE_CHECKING:
    from kaizen.service.client import ServiceClient

__all__ = ["AgentBundle", "build_agent", "handle_remote_command", "run"]


async def _maybe_init(memory: object) -> None:
    init = getattr(memory, "init_db", None)
    if init is not None:
        await init()


def _handle_command(line: str, bundle: AgentBundle) -> bool:
    """Return True if ``line`` was a slash-command (and consumed)."""
    cmd, _, arg = line.strip().partition(" ")
    if cmd == "/proposals":
        pending = bundle.queue.pending()
        if not pending:
            print("(no pending proposals)\n")
            return True
        for p in pending:
            payload = getattr(p.payload, "action", None) or getattr(p.payload, "name", "")
            print(f"  [{p.id[:8]}] {p.kind:8s} conf={p.confidence:.2f}  {payload}")
            print(f"           why: {p.rationale}")
        print()
        return True
    if cmd in {"/approve", "/reject"}:
        if not arg.strip():
            print(f"usage: {cmd} <id-prefix>\n")
            return True
        match = next(
            (p for p in bundle.queue.pending() if p.id.startswith(arg.strip())),
            None,
        )
        if match is None:
            print(f"no pending proposal matches '{arg.strip()}'\n")
            return True
        if cmd == "/approve":
            bundle.queue.approve(match.id)
            note = apply_approval(
                match,
                bundle.learned_traits,
                bundle.skills,
                state=bundle.state,
                instincts=bundle.instincts,
            )
            print(f"{note}\n")
        else:
            bundle.queue.reject(match.id)
            print(f"rejected {match.id[:8]}\n")
        return True
    if cmd == "/traits":
        if not bundle.learned_traits:
            print("(no learned traits yet — approve an instinct to add one)\n")
        else:
            for trait in bundle.learned_traits:
                print(f"  - {trait}")
            print()
        return True
    if cmd == "/skills":
        for spec in bundle.skills.specs():
            print(f"  - {spec['name']}: {spec['description']}")
        print()
        return True
    if cmd == "/help":
        print(_HELP)
        return True
    return False


_HELP = (
    "  /proposals          list pending proposals\n"
    "  /approve <id>       approve a proposal\n"
    "  /reject  <id>       reject a proposal\n"
    "  /traits             show learned-voice traits\n"
    "  /skills             show active skills\n"
    "  exit | quit         leave\n"
)


async def handle_remote_command(line: str, client: ServiceClient) -> str | None:
    """Client-mode twin of ``_handle_command``: same slash commands, over HTTP.
    Returns the text to print, or ``None`` if ``line`` is not a command."""
    cmd, _, arg = line.strip().partition(" ")
    if cmd == "/proposals":
        pending = await client.proposals()
        if not pending:
            return "(no pending proposals)\n"
        lines = []
        for p in pending:
            lines.append(f"  [{p['id'][:8]}] {p['kind']:8s} conf={p['confidence']:.2f}  "
                         f"{p['summary']}")
            lines.append(f"           why: {p['rationale']}")
        return "\n".join(lines) + "\n"
    if cmd in {"/approve", "/reject"}:
        if not arg.strip():
            return f"usage: {cmd} <id-prefix>\n"
        match = next(
            (p for p in await client.proposals() if p["id"].startswith(arg.strip())),
            None,
        )
        if match is None:
            return f"no pending proposal matches '{arg.strip()}'\n"
        if cmd == "/approve":
            decision = await client.approve(match["id"])
        else:
            decision = await client.reject(match["id"])
        return f"{decision['note']}\n"
    if cmd == "/traits":
        traits = await client.traits()
        if not traits:
            return "(no learned traits yet — approve an instinct to add one)\n"
        return "\n".join(f"  - {t}" for t in traits) + "\n"
    if cmd == "/skills":
        skills = await client.skills()
        return "\n".join(f"  - {s['name']}: {s['description']}" for s in skills) + "\n"
    if cmd == "/help":
        return _HELP
    return None


async def _chat_remote(client: ServiceClient) -> None:
    """Client-mode REPL: every turn goes over HTTP to the shared brain."""
    health = await client.health()
    brains = ", ".join(f"{tier}={name}" for tier, name in sorted(health["brains"].items()))
    session = await client.create_session(surface="cli")
    print(
        f"Kaizen CLI (client mode) — daemon at {client.base_url}, brains: {brains}, "
        f"memory: {health['memory']}, skills: {health['skills']}. "
        "Type /help for commands, 'exit' to quit.\n"
    )

    loop = asyncio.get_event_loop()
    try:
        while True:
            try:
                user = await loop.run_in_executor(None, input, "you> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if user.strip().lower() in {"exit", "quit"}:
                break
            if user.startswith("/"):
                out = await handle_remote_command(user, client)
                if out is not None:
                    print(out)
                    continue
            reply = await client.send(session["id"], user, author_id="local")
            print(f"kaizen> {reply['content']}\n")
    finally:
        await client.close()


async def _chat() -> None:
    from kaizen.service.client import connect

    settings = load_settings()
    client = await connect(settings.service_url)
    if client is not None:
        await _chat_remote(client)
        return
    print(f"(no daemon at {settings.service_url} — running embedded; "
          "start one with `python -m kaizen serve`)")

    bundle = build_agent(settings)
    await _maybe_init(bundle.loop.context.memory)

    brains = ", ".join(
        f"{tier.name.lower()}={provider.name}"
        for tier, provider in sorted(
            bundle.loop.router.providers.items(), key=lambda kv: kv[0].value
        )
    )
    learns = "on" if bundle.loop.scribe is not None else "off"
    print(
        f"Kaizen dev CLI — brains: {brains}, memory: {bundle.loop.context.memory.name}, "
        f"learning: {learns}, skills: {len(bundle.skills.list())}. "
        "Type /help for commands, 'exit' to quit.\n"
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
        if user.startswith("/") and _handle_command(user, bundle):
            continue
        reply = await bundle.loop.handle(
            bundle.session, Message(role=Role.USER, content=user, author_id="local")
        )
        print(f"kaizen> {reply.content}\n")


def run() -> None:
    if sys.argv[1:2] == ["serve"]:
        from kaizen.service.runner import serve

        serve()
        return
    asyncio.run(_chat())


if __name__ == "__main__":
    run()
