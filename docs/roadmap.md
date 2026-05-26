# Kaizen — Roadmap

The roadmap is deliberately staged so that the agent can begin contributing to its own development as early as possible.

## Phase 0 — Foundation (now)

- Design locked and documented (architecture, ADRs, this roadmap).
- Repo initialized and published (private, `mal0ware/Kaizen`).
- Decide GPU placement (Hetzner GPU vs home-GPU-over-Tailscale vs all-home).

## Phase 1 — Walking skeleton

- Headless core with the agent loop and a single surface (terminal UI).
- One provider working end-to-end: Anthropic API key.
- Minimal session store (so the loop is real, not a toy).

## Phase 2 — Memory

- Postgres + `pgvector` + Redis wired in.
- Structured facts + semantic recall + tiered storage.
- Ambient scribe doing passive extraction in the background.

## Phase 3 — Surfaces & continuity

- Discord gateway (own bot identity, Vixen's infra).
- Cross-surface session continuity (move a thread Discord ↔ terminal).

## Phase 4 — Local models & zero-config

- One-time-consent local-model setup (detect hardware → install Ollama → pull → wire).
- Graceful degradation: works with no paid subscription.
- Real-time triage + fast/slow response paths.

## Phase 5 — Identity graph

- Entity / account / belief model; reputation-vs-reality separation.
- Background entity resolution (multi-account merge, same-name disambiguation).

## MVP definition

Hetzner deployment live + local models running + core + Discord + terminal + Anthropic and local backends with one-time-consent setup. At this point Kaizen is usable day-to-day.

## Phase 6 — Self-design

Once the MVP runs, point Kaizen at its own design problems. The docs in this repo (architecture, design log, ADRs) are its working substrate: it reads them, proposes changes, and drafts implementations — **gated**, proposals only, human-approved. Continuous improvement, applied to itself. This is the north star the staging above is built to reach quickly.

## Cross-cutting (every phase)

- **Safety/gates** in front of anything consequential from day one.
- **Profiling before optimizing**; move measured hot paths to `native/` (Rust/C++).
- **Update the design log + ADRs** whenever a decision changes — the design stays bulletproof only if the record stays current.
