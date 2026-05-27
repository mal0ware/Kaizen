# ADR 0003 — Platform-agnostic identity & relationship graph

- **Status:** Accepted
- **Date:** 2026-05-26

## Context

Kaizen needs to model people for a human-feeling experience — including people who are *talked about but never present*, people with *several accounts*, and the case of *two different people with the same name*. Crucially, a person's **reputation** (how others see them) must stay separate from how they **actually are**. This cannot be a Discord-only construct.

## Decision

A graph with three kinds of node/edge:

- **Entity** — a real person/thing. May be absent (a discussed-but-never-present character is still an entity).
- **Account / handle** — an observed identity on a platform (Discord account, terminal user, email). Linked to an entity with a **confidence score**; links are **reversible**.
- **Belief / relationship edge** — `observer → subject`, holding *that observer's* point of view.

**Reputation ≠ reality:** objective, Kaizen-observed facts attach to the **entity**; each observer's opinions attach to **that observer's belief edges**. Reputation is the aggregate of observer beliefs, never merged into the entity's ground truth.

**Entity resolution** (ongoing, background, confidence-scored, reversible):
- Many accounts → one entity: merge on shared IDs, writing-style embeddings, explicit cues, shared context.
- Same name ≠ same entity: names are **attributes of accounts**, never identity. Never merge on name alone.
- The Discord snowflake ID is a strong signal but only one; resolution works across platforms.

Storage: relational node/edge tables in Postgres + `pgvector` for similarity. Dedicated graph DB deferred (overkill at this scale).

## Consequences

- Supports absent people, multi-account, and same-name disambiguation natively.
- Resolution is never assumed final — it's revisited as evidence accrues ("always improving").

## Consent posture

The operator asserts that all participants in their Discord server(s) have **consented** to being modeled. Under that assertion, full participant modeling (entities, accounts, beliefs, relationships) is **permitted** within the operator's servers. This is the operator's stated basis; if Kaizen is ever pointed at a space where that assumption doesn't hold, revisit before profiling.
