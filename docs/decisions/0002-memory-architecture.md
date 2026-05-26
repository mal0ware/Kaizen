# ADR 0002 — Structured, semantic, tiered memory with ambient learning

- **Status:** Accepted
- **Date:** 2026-05-26

## Context

The upstream approach (flat `MEMORY.md`/`USER.md` + SQLite FTS5) is the weakest part of the reference design: FTS5 is **lexical** (keyword) recall, not semantic; and a hard size cap forces the agent to *forget* to learn. Separately, the operator dislikes "conversation-as-training" — having to deliberately talk to the agent to build its memory.

## Decision

- **Stores:** Postgres for structured facts and graph edges; `pgvector` for semantic recall; Redis for hot working state. (Reuses Vixen's proven stack.)
- **Structured facts:** typed records — `(subject, attribute, value, confidence, source, first_seen, last_seen)`. Update individual facts in place; decay stale ones; resolve conflicts by recency/confidence.
- **Semantic recall:** a local embedding model vectorizes memories so recall is by meaning, not keywords.
- **Tiered, no hard-forget:** hot (small distilled profile, always in context) → warm (everything, semantically searchable) → cold (summarized archive). Demote and compress instead of deleting.
- **Ambient background learning:** a **scribe** worker passively reads the streams Kaizen is in, batches messages, and uses a cheap local model to extract candidate facts/updates into memory. Using Kaizen and teaching it are decoupled — no deliberate training conversations.

## Consequences

- Recall quality and "knows me" feel improve substantially over flat markdown.
- Embedding is a high-volume path → a likely first candidate for a native hot path (ADR 0001).
- Memory is operator data and is **never committed** to the repo (see `.gitignore`).
