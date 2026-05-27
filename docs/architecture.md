# Kaizen — Architecture

The consolidated system design. Individual decisions and their rationale live in [decisions/](decisions/) (ADRs); the chronological record of how we got here is in [design-log.md](design-log.md).

## Overview

Kaizen is a single **headless core** — the reasoning engine, memory, and identity graph — fronted by interchangeable **surfaces** (Discord, terminal, later web). It learns continuously and passively, models the people it encounters, orchestrates local and cloud models by cost and difficulty, and responds at conversational pace while knowing when to slow down and think.

## Headless core & surfaces

"Headless" means the core has **no UI of its own**. It runs as a long-lived service exposing an internal API; every way you talk to Kaizen is a thin client of that service.

- **Core (headless):** agent loop, orchestration/router, memory, identity graph, skills, safety/gates. Always running (on Hetzner).
- **Surfaces (clients):**
  - **Discord gateway** — always-on presence via `discord.py`. Its own bot identity, separate from Vixen but sharing infra.
  - **Terminal UI** — a "pretty" CLI (Rich for rendering, prompt_toolkit for input), in the spirit of Claude Code. Runs on any machine, connects to the core.
  - **Web pane** — later.

Why this matters: the brain is one thing; the faces are swappable. It's what makes the next point possible.

## Session continuity across surfaces

A conversation is a **session object owned by the core**, not by any surface. Any surface can attach to a session; context (recent turns + retrieved memory) is assembled by the core, so:

- You can move a thread from Discord to the terminal mid-conversation and Kaizen still knows what you're talking about.
- Two live conversations on different surfaces share the same underlying understanding (same memory, same identity graph), even concurrently.

Mechanism: sessions and turns persist in the core's store; surfaces send/receive turns over the internal API; the context engine merges per-session history with cross-session recall.

## Memory

Replaces the flat-markdown approach with a structured, semantic, tiered store. See [ADR 0002](decisions/0002-memory-architecture.md).

- **Stores:** Postgres for structured facts and graph edges; `pgvector` for semantic (meaning-based) recall; Redis for hot working state.
- **Structured facts:** typed records with `confidence`, `source`, `first_seen`, `last_seen`. Individual facts update without rewriting a blob; stale facts decay; conflicts resolve by recency/confidence.
- **Tiers (no hard-forget):** hot (a small distilled profile always in context) → warm (everything, semantically searchable) → cold (summarized archive). Nothing is deleted to make room; it's demoted and compressed.
- **Ambient learning:** a background **scribe** worker passively reads the streams Kaizen is in, batches messages, and uses a cheap local model to extract candidate facts/updates into memory. Learning is decoupled from foreground use — you never have to "have a conversation" to teach it.

## Identity & relationship graph

Platform-agnostic, not Discord-bound. See [ADR 0003](decisions/0003-identity-and-relationship-graph.md). Three node/edge kinds:

- **Entity** — a real person/thing. May be *absent* (a character everyone talks about but who never appears still gets an entity).
- **Account / handle** — an observed identity on some platform (a Discord account, a terminal user, an email). Linked to an entity with a confidence score; links are reversible.
- **Belief / relationship edge** — `observer → subject`, holding *that observer's* point of view.

The core principle: **reputation ≠ reality.** Objective, Kaizen-observed facts attach to the *entity*. Each observer's opinions attach to *that observer's belief edges*. So an absent character is an entity populated only by others' beliefs; a person's reputation is the aggregate of observer beliefs, kept distinct from how they actually are.

Entity resolution (ongoing background job — "always improving"):
- **Many accounts → one entity** (someone with several Discord accounts): merge on signals — shared IDs, writing-style embeddings, explicit "this is X" cues, shared context — confidence-scored and reversible.
- **Same name ≠ same entity** (two different people, one name): names are *attributes of accounts*, never identity. Never merge on name alone; disambiguate by behavior/context.
- The Discord snowflake ID is a strong signal but only one signal; the model works across platforms.

Storage: relational node/edge tables in Postgres (+ pgvector for similarity). A dedicated graph DB is deferred — overkill at this scale.

## Real-time response & thinking

"Think before you speak," at conversational pace. See [ADR 0005](decisions/0005-realtime-response-and-thinking.md).

Pipeline per incoming message:
1. **Ingest** → always absorbed into memory (background).
2. **Triage (cheap, local):** should I respond? how urgent? how hard/high-stakes? Most messages stop here (absorbed, not answered).
3. **Respond, two paths:**
   - **Fast path** — simple/low-stakes turns get a quick local reply to keep pace.
   - **Slow path** — hard/high-stakes turns escalate to the frontier model with extended thinking, after **verifying facts** against memory (retrieve before asserting; low confidence or conflict → think longer, search, or ask).
4. **Latency budget:** target a natural pace; when thinking will run long, show a typing indicator or send a brief interim ack — human turn-taking.

This is the local/cloud orchestration applied to *latency and depth*: cheap triage on everything, expensive deliberation only when warranted.

## Models & setup

See [ADR 0006](decisions/0006-model-strategy-and-setup.md).

- **Options:** local models (auto-installed) plus cloud. Mal's primary backend is his **Anthropic API key**.
- **Graceful degradation:** works even with no paid subscription — falls back to a local model. Always works.
- **One-time consent setup:** with a single yes, Kaizen detects hardware, picks an appropriate model size, installs the runtime (Ollama), pulls the model, and wires it up. No manual `.env` surgery; manual override available.

## Tools, world-awareness & Hermes integration

**Tools** ([ADR 0009](decisions/0009-tooling-and-skills.md)): web search, YouTube transcripts, financial data (OpenBB), and document RAG. All I/O-bound, so implemented in Python; the pattern is cheap/free fetch → local model digests/embeds → frontier reasons only when needed. Tools plug into a core-defined tool/skill interface.

**World-awareness** ([ADR 0011](decisions/0011-world-awareness-and-initiation.md)): a background world/news/market feed, a local relevance model scoring items against the operator's positions/projects/people, a temporal model tracking upcoming dated events, and a high-bar proactive-initiation policy that can break silence when something important crosses the bar.

**Hermes integration** ([ADR 0010](decisions/0010-hermes-integration.md)): observability over Hermes telemetry, decision journaling, a plain-language RiskAdvisory voice, and an adversarial analyst that challenges trade theses and surfaces qualitative/event factors the quant model is blind to — all behind a **hard execution wall** (Kaizen never executes trades, moves money, or influences the validation gate).

## Deployment

Resolved topology (see [ADR 0007](decisions/0007-compute-topology.md)): **always-on core + on-demand GPU worker + cloud floor.**

- **Core (always-on):** a small Hetzner Cloud instance with no GPU (CPX21/CX32 class, ~4–8GB RAM) hosts the loop, router, Postgres + pgvector + Redis, and the Discord gateway. The core is I/O-bound, so this is plenty.
- **Home GPU worker (on-demand):** the operator's desktop (RTX 3080, i9-13900k, 64GB) is a Tier-0 inference worker — local 7–8B 4-bit models, embeddings, triage, scribe. It is *not* always on and is never a dependency.
- **Networking:** Tailscale (WireGuard mesh) privately connects the VPS to the home worker.
- **Wake-on-LAN:** the core wakes the sleeping desktop via an always-on home-LAN **wake relay** (router or Raspberry Pi) reached over Tailscale; the worker auto-starts and registers on wake.
- **Latency hiding / fallback:** if the worker is asleep/unreachable/waking, respond immediately via cloud and queue heavy local-eligible jobs for when it's up.
- **Routing tiers:** Tier 0 local (free, high-volume) → Tier 1 cheap cloud → Tier 2 frontier (Opus, rare/hard). The router picks by difficulty/stakes (ADR 0005).
- **Worker pool:** any machine running a worker can join; the router distributes *jobs*, not a single model's layers.
- Terminal surface runs anywhere and connects back to the core.
- No hardware purchase required to start; a dedicated home server is a later option if usage justifies it.

## Cost & scale

**Cost:** the local-first funnel keeps the bulk near-free; tiered routing reserves frontier models for rare hard tasks. Disciplined run-rate ~$55–120/mo. The Max subscription is separate from the metered API. See [ADR 0008](decisions/0008-cost-and-billing.md).

**Scale:** a years-old, millions-of-message, ~10-person Discord is handled by a one-time local **backfill** → `pgvector` RAG + tiered summaries — history is an indexing problem, not a context-window problem. Multi-party interjection is the main hard problem. See [ADR 0012](decisions/0012-scale-backfill-multiparty.md).

## Repo organization

```
kaizen/
├── kaizen/                  # main Python package
│   ├── core/                # agent loop, context engine, session mgmt
│   ├── orchestration/       # routing, cloud/local split, triage, budgets
│   ├── providers/           # model adapters (Anthropic, local engines)
│   ├── memory/              # structured + semantic + tiered store, scribe
│   ├── identity/            # entity/account/belief graph, resolution
│   ├── curator/             # gated self-improvement loop (proposals only)
│   ├── skills/              # procedural skills
│   ├── surfaces/            # discord gateway, terminal UI, (web)
│   ├── integrations/        # external systems (e.g. Hermes trading ops)
│   ├── safety/              # redaction, sanitization, approval gates
│   └── cli/                 # terminal entry point
├── native/                  # Rust/C++ hot-path modules (bindings) — when profiled
├── docs/
│   ├── architecture.md
│   ├── design-log.md
│   ├── design-plan.md
│   ├── decisions/           # ADRs
│   └── research/            # upstream evaluation, notes
└── tests/
```

## Language & performance

Python for orchestration; Rust/C++ for proven hot paths via bindings, batched at the boundary, after profiling. Full reasoning in [ADR 0001](decisions/0001-language-and-performance.md). Likely first hot-path candidates: ambient ingestion/embedding, semantic search, real-time triage.

## Provenance

Kaizen is a **clean reimplementation** inspired by existing agent harnesses (Hermes Agent, OpenClaw studied as references — see [research/upstream-evaluation.md](research/upstream-evaluation.md)). No third-party source is copied, so no attribution is owed; Kaizen is its own project. If any third-party code is ever vendored, its license notice will be added at that point.

## Privacy

Modeling other people (their beliefs, reputations, relationships) is sensitive. Default posture: deep profiling is scoped to the operator; modeling of others is limited and deliberate. This is an explicit, revisited design constraint, not an afterthought.
