# Kaizen

A personal, always-on, self-improving AI agent. One mind, many surfaces.

**Kaizen** (改善 — "continuous improvement") lives on a server, learns continuously from everything around it, and gets a little better at *you* every cycle. You reach it from Discord or a terminal, and it keeps one shared understanding across both.

## What it is

- **Headless core, many surfaces.** A long-lived engine (reasoning + memory + identity) with no UI of its own. A Discord gateway, a terminal UI (Rich + prompt_toolkit), and — later — a web pane are thin clients that attach to the same brain. Move a conversation from Discord to the terminal mid-thought; it's the same session and the same context.
- **Always learning, in the background.** You don't "talk to it to train it." A background scribe passively distills the streams it sees into structured + semantic memory, on its own.
- **Knows people, not just text.** A platform-agnostic identity & relationship graph that separates who someone *is* from their *reputation* — what each observer believes about them.
- **Local + cloud, orchestrated.** Cheap local models do high-volume grunt work and real-time triage; your Anthropic API key handles hard reasoning. It works even with no paid subscription by falling back to a local model.
- **Thinks before it speaks.** Fast replies for simple turns; deliberate, fact-verified reasoning when stakes are high — and it knows which is which.

## Architecture at a glance

Surfaces are thin clients of one headless core. The core triages each message, routes it to a tier, runs tool rounds, then learns from the exchange in the background — with every self-state change held behind an operator approval gate.

```mermaid
flowchart TB
    subgraph surfaces["Surfaces (thin clients)"]
        cli["Terminal CLI"]
        discord["Discord gateway"]
        web["Web pane (later)"]
    end

    subgraph core["Headless core"]
        loop["Agent loop<br/>context → route → complete → tools"]
        triage["Triage<br/>(eval-graded heuristic)"]
        router["Router"]
        context["Context engine<br/>persona + tone + recall"]
        gate{{"Approval gate<br/>(self-state changes only)"}}
    end

    subgraph tiers["Provider tiers"]
        local["LOCAL · Ollama / mock"]
        cheap["CHEAP · Anthropic API"]
        frontier["FRONTIER · API / Claude Code sub"]
    end

    subgraph learn["Background learning"]
        scribe["Scribe<br/>(ambient fact extraction)"]
        curator["Curator<br/>(instinct / skill proposals)"]
    end

    subgraph memory["Memory + identity"]
        store[("MemoryStore<br/>in-memory · Postgres/pgvector")]
        identity[("Identity graph<br/>entity · account · belief")]
    end

    cli --> loop
    discord --> loop
    web -.-> loop

    loop --> triage --> router
    router --> local
    router --> cheap
    router --> frontier
    loop --> context --> store

    loop -.async.-> scribe --> store
    loop -.async.-> curator -->|proposal| gate
    gate -->|approved| context
    gate -->|approved| loop
    discord -.author_id.-> identity
```

## Run it in 60 seconds

The default configuration needs no API keys and no infrastructure: a deterministic mock provider and an in-memory store.

```bash
git clone https://github.com/mal0ware/Kaizen.git
cd Kaizen
pip install -e .
python -m kaizen
```

This starts a terminal REPL backed by the mock provider. Type `/help` for in-session commands and `exit` to quit. To run against real models or persistent memory, copy `.env.example` to `.env` and fill in the relevant values.

## Persistent memory (Postgres + pgvector)

When `KAIZEN_DATABASE_URL` is set, the memory store switches from the in-memory fallback to the Postgres + `pgvector` backend: facts are embedded and persisted, and recall is a cosine-distance similarity search over the vectors. Embeddings are produced by one of two embedders, selected with `KAIZEN_EMBEDDER`:

- `ollama` (default) — semantic embeddings from a local Ollama model (`nomic-embed-text`, 768-dim), free on the home GPU.
- `hash` — a deterministic, dependency-free embedder (the hashing trick) that needs no model, GPU, or network. Its recall is bag-of-words rather than semantic, but it makes the persistent-memory path runnable and reproducible with zero external services. The integration test below uses it.

### Live pgvector integration test

A reproducible script stands up pgvector in Docker, enables the `vector` extension, and runs the end-to-end memory test (write facts → similarity search → ambient-scribe write path) against the live database:

```bash
pip install -e ".[db]"        # asyncpg, sqlalchemy, pgvector
./scripts/pgvector-test.sh     # up -> migrate -> test -> down   (PowerShell: ./scripts/pgvector-test.ps1)
```

The script uses [`deploy/docker-compose.pgvector-test.yml`](deploy/docker-compose.pgvector-test.yml) (image `pgvector/pgvector:pg16`, host port `5433` so it never clashes with an existing Postgres, ephemeral storage). To point the suite at any other pgvector instance, set the URL yourself and run the marked tests directly:

```bash
KAIZEN_TEST_DATABASE_URL=postgresql+asyncpg://kaizen:kaizen@127.0.0.1:5433/kaizen \
  python -m pytest tests/integration -v
```

The `tests/integration` suite is skipped automatically when `KAIZEN_TEST_DATABASE_URL` is unset, so the default offline suite runs with no infrastructure.

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

Runnable skeleton. The core subsystems are implemented and covered by 108 offline tests, plus a live pgvector integration suite (111 total when a database is present):

- **Agent loop** — context assembly, routed completion, tool rounds, and background scribe/curator passes.
- **Tiered routing** — local / cheap / frontier tiers with per-message triage.
- **Providers** — Anthropic API, Claude-CLI subprocess (subscription auth), local Ollama-compatible endpoint, and a deterministic mock for zero-key development.
- **Memory** — in-memory store by default; Postgres + pgvector backend when configured, proven end to end against a live database by the integration suite (see [Persistent memory](#persistent-memory-postgres--pgvector)).
- **Curator** — proposes learned traits and skills from conversation; every change is held in a queue behind an operator approval gate.
- **Discord surface** — gateway bot sharing the same agent core as the CLI.
- **Deploy scaffolding** — Docker Compose, systemd units, provisioning and backup scripts under [`deploy/`](deploy/).

Kaizen is a clean reimplementation inspired by existing agent harnesses — no third-party code is copied. License: MIT — see [LICENSE](LICENSE).
