# ADR 0012 — Scale, history backfill & multi-party conversations

- **Status:** Accepted
- **Date:** 2026-05-26

## Context

Primary use is a Discord server that may be **years old with millions of messages**, with **~10 people talking at once regularly** and high text volume. This is bigger than single-operator scale.

## Decision

**History is an indexing problem, not a context problem.**
- One-time **backfill**: ingest history → embed locally → store in `pgvector`. Retrieval (RAG) pulls only the relevant handful per query. Tiered memory (ADR 0002) summarizes/compresses the cold bulk so the working set stays small.
- **Backfill math:** ~2M messages embed in ~30–60 min on the 3080 (batched small embedding model); ~6 GB of vectors + index. HNSW search stays in single-digit/low-tens of ms at multi-million scale.
- The index wants to live in RAM → 16 GB VPS (ADR 0013).

**Multi-party conversation** (the genuinely hard part — an ML/UX problem, not a cost one):
- Per-speaker attribution via Discord IDs; the identity graph (ADR 0003) tracks each speaker.
- Multi-thread topic tracking within a single fast-moving channel.
- High-bar **interjection governor** (ADR 0005) — in a 10-person chat the bar to speak unprompted must be high, with the pre-send relevance re-check so contributions stay timely and meaningful.

**Consent:** the operator asserts all Discord participants have consented → full participant modeling is permitted within the operator's servers.

**Scale escape hatch:** a dedicated vector DB (Qdrant / Milvus) only if `pgvector` is ever outgrown — not needed at single-server scale.

## Consequences

- Years of history become fast, searchable memory rather than a context-window problem.
- Multi-party interjection quality is the main hard problem to prototype carefully.
