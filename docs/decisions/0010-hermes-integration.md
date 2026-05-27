# ADR 0010 — Hermes integration & the execution wall

- **Status:** Accepted
- **Date:** 2026-05-26

## Context

Kaizen connects to the Hermes trading platform (both Python). The connection must be *meaningful* — not "another chatbot" — without becoming a risk to capital.

## Decision

Kaizen is the **operator interface, memory, and analyst around Hermes — never a trading brain.** Roles:

1. **Observability** — ingest Hermes telemetry (fills, positions, risk metrics, validation-run output); the local model watches the firehose and surfaces only what matters (DSR crossings, drawdown nearing limits, run summaries).
2. **Decision memory / journaling** — log every trade and parameter choice *with its rationale*; recall later ("why did I size the IPO position this way?"). Decision provenance.
3. **Plain-language RiskAdvisory face** — the natural-language layer over Hermes's existing advise → discipline → vetoer gate; explain *why* the vetoer would block something before the operator acts.
4. **Adversarial analyst** — question trade logic, steelman the opposite thesis, argue for/against positioning and sizing, and surface qualitative/event/macro factors the quant model is structurally blind to. Fills the solo-operator's missing-cofounder perspective gap.
5. **Alerting** — DM the operator (Discord/Telegram) when Hermes needs attention.

## The hard wall (non-negotiable)

Kaizen **never** executes trades, moves money, places or cancels orders, alters strategy parameters, or influences the validation gate (DSR ≥ 0.95). It lives strictly on the **read-only / advisory** side. Execution and validation stay on Hermes's own gated, human-approved path.

Discipline: the adversary is a **structured challenger, not an oracle.** An LLM can be confidently wrong or sycophantic; its value is forcing the operator to articulate and defend reasoning and exposing blind spots — an *input* to judgment, never an override of the validated quant edge.

## Consequences

- Makes the solo operator materially stronger (situational awareness, recall, red-team, alerting) without becoming a single point of failure for capital.
- The wall is what makes the integration safe enough to be worth doing.
