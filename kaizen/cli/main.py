"""Runnable dev CLI: ``python -m kaizen``.

Wires the core (router + memory + scribe) and the persona/learning stack
(curator + approval gate + proposal queue + skill registry + learned traits),
so it uses real providers/Postgres/ambient learning when configured and falls
back to mock + in-memory when nothing is set up — it always runs, infra or not.

In-session commands:
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

from kaizen.bootstrap import AgentBundle, build_agent
from kaizen.core.models import Message, Role
from kaizen.curator.apply import apply_approval

__all__ = ["AgentBundle", "build_agent", "run"]


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
        print(
            "  /proposals          list pending proposals\n"
            "  /approve <id>       approve a proposal\n"
            "  /reject  <id>       reject a proposal\n"
            "  /traits             show learned-voice traits\n"
            "  /skills             show active skills\n"
            "  exit | quit         leave\n"
        )
        return True
    return False


async def _chat() -> None:
    bundle = build_agent()
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
    asyncio.run(_chat())


if __name__ == "__main__":
    run()
