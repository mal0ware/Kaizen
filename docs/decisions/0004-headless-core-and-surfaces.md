# ADR 0004 — Headless core, thin surfaces, cross-surface continuity

- **Status:** Accepted
- **Date:** 2026-05-26

## Context

Kaizen must be usable in a "pretty" terminal (in the spirit of Claude Code), reachable from any machine, and able to **move a conversation between Discord and the terminal** while keeping one shared understanding — even with concurrent live conversations.

## Decision

- **Headless core:** the engine (loop, orchestration, memory, identity, safety) runs as a long-lived service with **no UI of its own**, exposing an internal API.
- **Thin surfaces (clients):**
  - **Discord gateway** — always-on, `discord.py`, its own bot identity (separate from Vixen, shared infra).
  - **Terminal UI** — Rich (rendering) + prompt_toolkit (input), the proven stack from the reference harness; runs anywhere, connects to the core.
  - **Web pane** — later.
- **Sessions owned by the core:** a conversation is a core-side session object; any surface can attach. Context = per-session history + cross-session memory recall, assembled by the core. This is what makes Discord↔terminal hand-off and concurrent shared understanding work.

## Consequences

- The brain is single and authoritative; faces are swappable and independent.
- A surface crashing never loses state (it lives in the core).
- Requires a clean internal API contract between core and surfaces from early on.
