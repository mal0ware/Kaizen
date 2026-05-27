# Kaizen

A personal, always-on, self-improving AI agent. One mind, many surfaces.

**Kaizen** (改善 — "continuous improvement") lives on a server, learns continuously from everything around it, and gets a little better at *you* every cycle. You reach it from Discord or a terminal, and it keeps one shared understanding across both.

## What it is

- **Headless core, many surfaces.** A long-lived engine (reasoning + memory + identity) with no UI of its own. A Discord gateway, a terminal UI (Rich + prompt_toolkit), and — later — a web pane are thin clients that attach to the same brain. Move a conversation from Discord to the terminal mid-thought; it's the same session and the same context.
- **Always learning, in the background.** You don't "talk to it to train it." A background scribe passively distills the streams it sees into structured + semantic memory, on its own.
- **Knows people, not just text.** A platform-agnostic identity & relationship graph that separates who someone *is* from their *reputation* — what each observer believes about them.
- **Local + cloud, orchestrated.** Cheap local models do high-volume grunt work and real-time triage; your Anthropic API key handles hard reasoning. It works even with no paid subscription by falling back to a local model.
- **Thinks before it speaks.** Fast replies for simple turns; deliberate, fact-verified reasoning when stakes are high — and it knows which is which.

## Stack at a glance

- Python orchestration; Rust/C++ for proven hot paths — see [ADR 0001](docs/decisions/0001-language-and-performance.md).
- Postgres + `pgvector` (structured + semantic memory) and Redis (hot state) — same stack as Vixen.
- `discord.py` gateway; Rich + prompt_toolkit terminal UI.
- Deploys on **Hetzner**. Local-model GPU placement is an open decision — see [architecture](docs/architecture.md#deployment).

## Documentation

- [Architecture](docs/architecture.md) — the consolidated system design
- [Design log](docs/design-log.md) — every decision, what changed, and why
- [Decisions (ADRs)](docs/decisions/) — settled choices, one per file
- [Design plan](docs/design-plan.md) — every component, its method, and how they fit together
- [Upstream evaluation](docs/research/upstream-evaluation.md) — the harnesses studied as reference

## Vision

Get the Hetzner deployment and local models running as an MVP, then point Kaizen at its own design problems — using this documentation as its working substrate — so it participates in designing itself. Continuous improvement, applied recursively.

## Status

Early. Foundation and design locked; implementation not yet started. Kaizen is a clean reimplementation inspired by existing agent harnesses — no third-party code is copied. License: TBD.
