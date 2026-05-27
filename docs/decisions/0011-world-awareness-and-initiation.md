# ADR 0011 — World-awareness & proactive initiation

- **Status:** Accepted
- **Date:** 2026-05-26

## Context

Kaizen should track timelines and world events, and break silence when something important happens — even if the Discord is quiet — without becoming noisy.

## Decision

Four cooperating pieces:

- **World feed** — background ingestion of news / market / event streams (RSS, news + market-data APIs, optionally social). Continuous, local.
- **Relevance model** — the local model scores each item against what the operator cares about: positions, watchlist, projects, and the people/topics in memory.
- **Temporal model** — events are timestamped into memory; Kaizen tracks *upcoming* dated events (IPO dates, earnings, deadlines) and anticipates, not just reacts ("SpaceX IPO in 3 days").
- **Proactive-initiation policy** — silence is *not* a reason to stay silent. An item that crosses a high relevance+importance bar can *open* a conversation, but rate-limited and high-bar so it never becomes spam.

## Cost

Ingestion + relevance scoring run local (≈ free). Cloud fires only to compose a substantive proactive message.

## Consequences

- Always-on situational awareness tied to the operator's actual interests and positions.
- Pairs with the interjection governor (ADR 0005): same "only contribute when it meaningfully makes sense" discipline, applied to unprompted messages.
