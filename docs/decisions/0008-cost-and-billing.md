# ADR 0008 — Cost model & billing strategy

- **Status:** Accepted
- **Date:** 2026-05-26

## Context

The operator pays $200/mo for Claude Max, which is billed **separately** from the Anthropic API (Max covers the Claude apps + Claude Code; the API is metered pay-per-token). We want to minimize net-new spend and not waste the Max subscription.

## Decision

- **Local-first funnel keeps the bulk near-free.** High-volume tasks (triage, embeddings, scribe, simple replies) run on the home 3080 at ~$0.50/M-token in electricity. Most volume never touches cloud.
- **Tiered routing:** Tier 0 local → Tier 1 cheap cloud → Tier 2 frontier (Opus, rare). Router decides by difficulty/stakes (ADR 0005).
- **Operator's personal lane uses Max via Claude Code auth.** Harnesses can authenticate Anthropic through the Claude Code subscription path (not just an API key). For Mal's *own* interactive/deep sessions (terminal, dev), use that — leverages the $200 already paid, legit personal use.
- **Autonomous / multi-user Discord traffic uses the metered API.** Do **not** route the public multi-user bot through the personal Max subscription — it's a ToS gray area and will hit subscription rate limits. The funnel keeps this API spend small.
- **Budget guards** (iteration/token budgets, ADR 0001 references) enforce ceilings so cost can't run away.

## Cost estimate (approximate; verify current rates)

Per-million-token cost by tier: local ~$0.50 (electricity) · cheap cloud ~$1–4 · mid (Sonnet) ~$3 in/$15 out · frontier (Opus) ~$15 in/$75 out — a ~30–150× spread, which is the entire economic case for the hybrid.

| Item | Assumption | $/mo |
|---|---|---|
| VPS core | Hetzner CPX41 | ~$30 |
| Home electricity | incremental, bursty GPU | ~$5–10 |
| API (Tier 1+2) | disciplined; Opus rare | ~$20–80 |
| **Run-rate** | | **~$55–120** |

Opus usage is the swing variable. Frugal months land ~$35–45; Opus-happy months exceed $150.

## Consequences

- Max keeps its value; net-new spend stays low because local does the grunt and API only gets escalations.
- Cost is a discipline problem (the Opus dial), not a scale problem.
