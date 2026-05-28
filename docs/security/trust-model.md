# Kaizen — trust model

_One page. The point is to make every implicit assumption explicit so the
gates that follow have a clear thing to enforce._

## Principals

- **Operator (Mal).** Single, trusted. Kaizen exists to serve him; he can do
  anything the system can do. Authorization questions reduce to "is this
  actor the operator?"
- **Kaizen itself.** Trusted to plan, propose, draft, ingest, retrieve. Not
  trusted to *self-apply* changes to its own skills, memory, or — for
  Hermes — to anything that touches money or strategy. The agent is honest
  but architecturally restrained.
- **Third parties** (people speaking to Kaizen via Discord, document
  authors, web pages, world-feed sources, model providers). **Untrusted.**
  Their content can carry adversarial instructions; treat as data, never as
  control. Identity assertions about third parties are *beliefs*, not facts
  (ADR 0003).

## What Kaizen may do unprompted

- **Read:** any of its own state, any operator-shared content, any external
  source it was configured to ingest.
- **Think / draft:** any internal reasoning, prompt drafts, plan documents,
  proposal payloads. Draft ≠ effect.
- **Speak:** respond when addressed; initiate only when the world-awareness
  initiation policy clears (ADR 0011).

## What requires the approval gate

Anything that mutates persistent state or external systems passes through
`kaizen.safety.ApprovalGate`. Concretely today:

- `skill.write`, `skill.archive` — curator-authored skills
- `memory.edit`, `memory.delete` — operator-scoped memory changes
- `instinct.promote` — pending → active
- `proposal.apply` — applying any approved proposal payload

`ApprovalGate.requires_approval(action)` is the policy; the gate is the
single chokepoint. Nothing in `curator/` self-applies; the proposal queue
composes the gate (does not duplicate it).

## What is architecturally walled off (no gate, no exceptions)

- **Hermes execution.** Kaizen never places trades, moves money, alters
  strategy parameters, or touches the validation gate (DSR ≥ 0.95).
  Integration is read-only toward execution (ADR 0010 / design-plan §Hermes).
  Advisor, not oracle.

## Ingest-time defenses

- **Redaction** (`kaizen.safety.redact`) runs on all third-party content
  before it reaches the scribe or identity graph. Catches obvious credential
  shapes (`sk-…`, `ghp_…`/`github_pat_…`, `AKIA…`, `Bearer …`, opaque
  long blobs) and replaces them with `«redacted:KIND»` markers. The bias is
  toward over-redaction in the catch-all `opaque` rule: a false positive
  on a hash is a cosmetic loss; a leaked API key is not.
- **Prompt-injection posture.** Third-party content is *data*. The loop
  never lifts instructions out of ingested content into the system prompt.
  Tools that fetch external content (search results, transcripts, docs)
  return strings; only operator-issued or system-issued messages drive
  behaviour.

## Out of scope for this document

Network policy, secret storage on the VPS, Tailscale ACLs, Postgres role
hardening, and Discord bot scopes — operational security, not the
in-process trust model. Tracked separately.

## External audit

Run `npx ecc-agentshield scan` against this repo and the Hermes repo from
time to time — it's `npx`, zero install, and surfaces secret leaks,
permission audits, and hook-injection patterns across CLAUDE.md / settings
/ MCP / hooks / agents.
