# Kaizen — Design Log

A chronological record of design decisions: what was discussed, what was decided, what changed, and *why*. The goal is a bulletproof, auditable design — anyone (including a future Kaizen working on itself) can read this and understand not just the current design but the reasoning and the discarded alternatives.

> **Scope note:** this log captures the *design* conversation only. Unrelated personal context from the discussions that produced these decisions is deliberately excluded for privacy. Decisions, rationale, and trade-offs are recorded; off-topic material is not.

> **Convention:** every settled decision also gets an ADR in [decisions/](decisions/). This log is the narrative; ADRs are the structured record. When a decision changes, update the relevant ADR's status and add a dated entry here explaining the change.

---

## 2026-05-26 — Project created

- Kaizen established as a project **separate** from the Hermes trading platform, to avoid the three-way name collision (Hermes trading platform / Nous's Hermes Agent / this). Repo lives at `Github Stuff/Kaizen`, a sibling of Hermes.
- Name chosen for meaning: *kaizen* = continuous incremental improvement, matching the self-improving premise.

## 2026-05-26 — Upstream evaluation (Hermes Agent vs OpenClaw)

- Cloned and compared both harnesses (see [research/upstream-evaluation.md](research/upstream-evaluation.md)).
- **Hermes Agent** — Python, MIT, depth/self-improvement, no reported CVEs, clean modular subsystems. **OpenClaw** — huge TS/Node monorepo, breadth, desktop apps, historical CVEs from its large surface area.
- **Decision:** model Kaizen on Hermes Agent's design (Python, self-improving loop, agent-curated memory) rather than OpenClaw's breadth-first approach.

## 2026-05-26 — Language & performance (ADR 0001)

- Considered building in C++/Rust for speed, especially for local models.
- **Resolved:** a harness is **I/O-bound** — it waits on the GPU or network — so harness language barely affects inference speed; that speed lives in the inference engine (llama.cpp/vLLM, already native). Decision: **Python orchestration, Rust/C++ for proven hot paths** via bindings, batched at the boundary, **after profiling**. Rust preferred for new native modules (safety, clean PyO3 bindings, already used in Hermes).

## 2026-05-26 — From "fork" to "clean reimplementation"

- Initially framed as forking Hermes Agent. Mal wanted Kaizen to be genuinely its own thing and to carry no attribution.
- **Clarified the legal reality:** copying MIT code requires retaining the copyright notice; *reimplementing the ideas* in fresh code owes nothing (architecture/concepts aren't copyrightable).
- **Decision:** Kaizen is a **clean reimplementation** — study the upstreams as reference, write our own code, copy no source. `NOTICE.md` retired accordingly. (If any third-party code is ever vendored, add its notice at that time.)

## 2026-05-26 — Memory architecture (ADR 0002)

- Hermes's flat `MEMORY.md`/`USER.md` + lexical FTS5 search identified as the weakest link (keyword-only recall; hard size cap forces forgetting).
- **Decision:** structured facts + **semantic** recall (`pgvector`) + **tiered** memory (hot/warm/cold, no hard-forget) on Postgres/Redis (Vixen's stack). Plus **ambient background learning** — a scribe distills the stream into memory passively, because Mal dislikes conversation-as-training; using Kaizen and teaching it are decoupled.

## 2026-05-26 — Identity & relationship graph (ADR 0003)

- Requirement sharpened: identity must be **platform-agnostic** (not Discord-bound), must model **absent** people (characters everyone discusses), must separate **reputation from reality**, and must handle **multiple accounts per person** and **same name ≠ same person**.
- **Decision:** Entity / Account / Belief model. Objective facts on the entity; each observer's POV on that observer's belief edges. Entity resolution as an ongoing, confidence-scored, reversible background job. Discord snowflake is one signal among many.
- **Constraint:** profiling of *other* people is sensitive; default-scope deep profiling to the operator.

## 2026-05-26 — Headless core, surfaces & continuity (ADR 0004)

- Requirements: use it in a "pretty" terminal like Claude Code; reach it from any machine; move a conversation Discord↔terminal; keep one understanding across concurrent live conversations.
- **Decision:** **headless core** (no UI) + thin **surfaces** (Discord gateway, Rich/prompt_toolkit terminal UI, later web). Sessions owned by the core so any surface can attach and context stays unified. Discord surface gets its own bot identity, shares Vixen's infra.

## 2026-05-26 — Real-time response & thinking (ADR 0005)

- Requirements: respond at conversational pace, verify facts, and know when to "think longer" (like Claude's extended thinking).
- **Decision:** per-message cheap local **triage** → **fast path** (quick local reply) vs **slow path** (frontier + extended thinking + fact verification against memory). Latency budget with typing/interim acks. Orchestration applied to latency and depth.

## 2026-05-26 — Model strategy & setup (ADR 0006)

- Requirements: local + cloud options; Anthropic API key as Mal's primary; must work without a paid subscription; one-time-consent auto-setup of a local model (no manual configuration).
- **Decision:** multi-provider with graceful degradation to local; **one-time consent** flow that detects hardware, picks a model size, installs Ollama, pulls a model, and wires it up.

## 2026-05-26 — Deployment target & infra constraint

- **Hetzner** chosen as the VPS. Reuse Vixen's stack (Python, `discord.py`, Postgres, Redis).
- **Open decision:** local models need a GPU that a cheap Hetzner VPS lacks. Options recorded in [architecture.md#deployment](architecture.md#deployment); leaning toward core-on-Hetzner + local inference on a home GPU box over Tailscale/Twingate. **To be settled before the MVP build.**

## 2026-05-26 — North star: self-design

- Once the MVP is up (Hetzner + local models + core + Discord + terminal), point Kaizen at its own design problems, using these docs as its working substrate, so it helps design itself — gated proposals only. Captured in [roadmap.md](roadmap.md).
