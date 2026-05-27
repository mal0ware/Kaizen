# ADR 0009 — Tooling & skills

- **Status:** Accepted
- **Date:** 2026-05-26

## Context

Kaizen needs to search the web, pull YouTube transcripts, fetch financial data, and read niche documents. Question raised: should these be written in C++ for speed, copying Hermes/OpenClaw implementations?

## Decision

- **Tools are implemented in Python, not C++.** They are **I/O-bound** — almost all their time is spent waiting on a network/API/disk, so native code buys nothing (per ADR 0001) and costs the Python ecosystem that makes them trivial. Notably, **OpenBB is a Python library**, so financial tooling integrates natively in Python and would need an awkward bridge from C++.
- **Tool set (initial):**
  - **Web search** — a search API (Brave / Exa / Tavily / Firecrawl).
  - **YouTube transcripts** — `youtube-transcript-api` (pulls captions directly, no LLM to fetch).
  - **Financial data** — OpenBB + market-data APIs + Hermes's own data.
  - **Document reading** — fetch → parse (pdfplumber / unstructured) → chunk → local embed → pgvector RAG.
- **Execution pattern:** cheap/free fetch → local model digests/embeds → frontier model reasons only when warranted.
- **Clean reimplementation:** study how Hermes Agent / OpenClaw structure their tool/skill *interfaces* as reference; write our own; copy no source.
- **Sequencing:** tools plug into a tool/skill interface defined by the core. That interface (and the package skeleton) come **first**; tools are written against it — not implemented standalone in an empty repo.
- **Only native candidate:** the high-volume embedding/ingest batch path (CPU/GPU-heavy), and only after profiling — never the fetch tools.

## Consequences

- Fast to build, ecosystem-rich, cheap to run.
- Keeps the "language doesn't matter for I/O-bound work" rule from ADR 0001 consistent.
