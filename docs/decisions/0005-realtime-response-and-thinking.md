# ADR 0005 — Real-time response with adaptive thinking

- **Status:** Accepted
- **Date:** 2026-05-26

## Context

Kaizen must respond at conversational pace in live chats, verify its facts before asserting them, and know when to **think longer** for hard or high-stakes questions — "think before you speak," like Claude's extended thinking — without keyword triggers.

## Decision

Per-message pipeline:
1. **Ingest** — every message is absorbed into memory (background), whether or not it's answered.
2. **Triage (cheap, local):** should I respond? how urgent? how hard / high-stakes? Most messages stop here.
3. **Respond, two paths:**
   - **Fast path** — simple/low-stakes turns get a quick local reply to keep pace.
   - **Slow path** — hard/high-stakes turns escalate to the frontier model with extended thinking, **after fact verification**: retrieve from memory before asserting; on low confidence or conflict, think longer, search, or ask rather than guess.
4. **Latency budget:** target a natural pace; when deliberation will run long, show a typing indicator or send a brief interim ack (human turn-taking).

A **social governor** wraps interjection: don't interrupt a live human-to-human exchange, respect cooldowns, rate-limit self-interjections, back off when ignored, expose a "talkativeness" dial.

**Interjection governor (pre-send re-check).** Triage runs fast, so Kaizen can *draft* an intervention that makes sense. But conversations move fast — by the time a draft is ready, the thread may have moved on. So in an **active conversation**, immediately before sending, Kaizen **re-validates the draft against the latest messages**: if it still makes sense and contributes meaningfully, send; if the conversation has moved past it, drop or revise. The bar is "does this still meaningfully contribute *right now*," checked at send-time, not just at draft-time. This is what keeps contributions timely and on-point in a fast multi-party channel.

## Consequences

- This is the local/cloud orchestration applied to **latency and depth** — cheap triage on everything, expensive deliberation only when warranted.
- High-stakes domains (e.g. trading) bias toward the slow, verified path by policy.
- Triage runs on every message → likely native hot-path candidate (ADR 0001).
