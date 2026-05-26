# ADR 0006 — Model strategy & one-time-consent setup

- **Status:** Accepted
- **Date:** 2026-05-26

## Context

Kaizen needs multiple model options (local + cloud), with the operator's **Anthropic API key** as the primary backend. It must keep working **even without a paid subscription**, and it must set up a local model **without manual configuration** — one consent, not a setup marathon.

## Decision

- **Multi-provider** behind one interface (ADR-0001 provider layer): Anthropic API (primary for the operator) + local engines (Ollama) + room for others.
- **Graceful degradation:** at boot, detect available backends (API keys? reachable local model? GPU?) and self-configure, always keeping a working fallback. No key → run local. Always works.
- **One-time-consent setup:** with a single yes, Kaizen detects hardware, picks an appropriate model size (small GPU → 4-bit 7B; larger GPU → bigger; no GPU → tiny CPU model or cloud-only), installs the runtime (Ollama), pulls the model, and wires it up. Manual override available but not required.

## Consequences

- Zero-config first-run experience; no `.env` surgery to get a working brain.
- Routing between local and cloud is decided by cost/difficulty (see ADR 0005), not hard-coded.
- Secrets (API keys) live in `.env`, never committed.
