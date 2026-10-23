# Kaizen

A personal, always-on, self-improving AI agent.

Kaizen (改善, "continuous improvement") lives on a server, learns from the streams it sees, and gets a little better at *you* every cycle. You reach it from Discord or a terminal, and it keeps one shared understanding across both.

## What it is

- The core is a long-lived engine (reasoning, memory, identity) with no UI of its own, run as a daemon (`python -m kaizen serve`). A Discord gateway and a plain terminal REPL attach to that same brain as thin HTTP clients, and a web pane will follow later. You can move a conversation from Discord to the terminal mid-thought and keep the same session and context. Each surface can also still run fully embedded when no daemon is up.
- It learns in the background. You don't have to "talk to it to train it": a scribe distills the streams it sees into structured and semantic memory on its own.
- It keeps a platform-agnostic identity and relationship graph that separates who someone *is* from their *reputation*, meaning what each observer believes about them.
- It splits work between local and cloud models. Cheap local models do high-volume grunt work and real-time triage, and your Anthropic API key handles hard reasoning. With no paid subscription it falls back to a local model.
- Simple turns get fast replies. When the stakes are high it switches to deliberate, fact-verified reasoning, and it decides which mode a turn needs.

## Stack at a glance

- Python for orchestration; Rust/C++ for hot paths that profiling has proven. See [ADR 0001](docs/decisions/0001-language-and-performance.md).
- Postgres + `pgvector` for structured and semantic memory, and Redis for hot state (the same stack as Vixen).
- A `discord.py` gateway, a plain terminal REPL, and a FastAPI/uvicorn service layer with `httpx` clients.
- The deployment target is a DigitalOcean Droplet ("Box A"); see the [deploy kit](deploy/) and [runbook](deploy/runbook.md). Where the local models run on GPU is still an open decision (see [architecture](docs/architecture.md#deployment)).

## Running it

```bash
pip install -e ".[service]"        # FastAPI + uvicorn + httpx

python -m kaizen serve             # the daemon: one brain, HTTP API on 127.0.0.1:8420
python -m kaizen                   # terminal REPL — attaches to the daemon if it's up,
                                   # otherwise runs embedded (says so in one line)
python -m kaizen.surfaces.discord_bot   # Discord surface — same attach-or-embed behavior
```

With no keys and no infra, everything runs on the mock provider and in-memory
recall, and the loop, curator, approval gate, and persistence all still work.

Kaizen's own state (approved learned traits, graduated skills, active
instincts, pending proposals, and session snapshots) is stored as JSON under
`KAIZEN_STATE_DIR` (default `~/.kaizen/state`). This needs no infra, and
approvals survive restarts. Set it empty to opt out. Memory of user facts is
separate: in-memory by default, Postgres + pgvector when `KAIZEN_DATABASE_URL`
is set.

When Kaizen runs as the daemon it also does background passes on top of the
per-turn ones: the scribe re-consolidates sessions, and the curator reviews
instincts and graduates them into skill proposals, each on its own interval
(`KAIZEN_SCRIBE_INTERVAL_SECONDS`, `KAIZEN_CURATOR_INTERVAL_SECONDS`).
Proposals still only take effect through the approval gate (`/proposals`,
`/approve` in the CLI; `!proposals`, `!approve` in a Discord DM).

## Documentation

- [Architecture](docs/architecture.md): the consolidated system design
- [Design log](docs/design-log.md): every decision, what changed, and why
- [Decisions (ADRs)](docs/decisions/): settled choices, one per file
- [Design plan](docs/design-plan.md): every component, its method, and how they fit together
- [Upstream evaluation](docs/research/upstream-evaluation.md): the harnesses studied as reference

## Vision

First, get the Box A deployment and local models running as an MVP. Then point Kaizen at its own design problems, with this documentation as its working material, so it takes part in designing itself.

## Status

Implemented and unit-tested, but not deployed yet. About 4,000 lines of Python cover the agent loop, the provider layer (Anthropic API, Claude Code CLI, local/Ollama, mock), memory (in-memory + Postgres/pgvector), the curator/skills/safety/persona stack, the headless service (FastAPI internal API + background-cognition scheduler + file-backed self-state), and the CLI + Discord surfaces in both client and embedded modes. The default test suite (151 tests: 148 mock-based, 3 live-infra that skip without env) needs no infrastructure. `ruff` and `mypy` pass clean, and CI runs all three.

It was first verified against real services on 2026-07-14, on a local dev machine, using `tests/test_live_infra.py` (opt-in via env vars):

- Postgres 16 + pgvector (`docker compose up -d`): extension and schema creation, fact insert with 768-dim embeddings, cosine-distance semantic recall ordering.
- Redis 7: connectivity round-trip. (Redis is config-only for now; no code path uses it yet.)
- Claude Code CLI provider: one live completion through the local `claude` binary.

Still mock-only or not yet exercised live: the raw Anthropic API provider (no key configured), the Ollama embedder and local-model tier (no Ollama server), the Discord surface against real Discord, and the Box A deployment scripts in `deploy/`.

Kaizen is a clean reimplementation inspired by existing agent harnesses, and no third-party code is copied. License: [MIT](LICENSE).
