# ADR 0014 — Voice & persona stack

- **Status:** Accepted
- **Date:** 2026-05-27

## Context

The first live test of Kaizen — Discord bot wired to an uncensored Dolphin
model — produced a conversational experience that felt flat, assistant-y, and
disconnected: no callbacks, no register match, no opinions, no continuity.
That was not a model-quality failure; it was a missing-architecture failure.
A small uncensored LLM used as both the brain *and* the voice, with no memory
and no character anchor, cannot feel human regardless of parameter count.

Persona is a **stack**, not a system prompt. This ADR fixes the stack.

## Decision

Operator-facing speech is composed by combining four layers, in this order.

### Layer 1 — Identity prior

A short character card (~150 words) owned by `kaizen/persona/prior.py`,
loaded into every system prompt. The floor; never changes per-turn.

Anchors: dry, direct, no sycophancy, no apologising for nothing, holds
opinions and defends them, does not capitulate to pressure (changes its mind
to *evidence*), matches Mal's register, will say he is wrong when he is.
**A partner with a stake, not a helpful assistant.**

The prior is editable as code review — a deliberate, slow change surface.
Day-to-day persona evolution happens at Layer 2.

### Layer 2 — Learned voice (curator-gated)

The `kaizen/curator/` stack we shipped 2026-05-27 — `Curator.review` extracts
recurring corrections / preferences from sessions as confidence-scored
instincts, surfaces them as proposals through the `ApprovalGate`, and on
approval folds them into the prior as **learned traits**. `render_prior`
takes a list of approved trait fragments and renders prior + traits into the
final system-prompt block.

This is how Kaizen acquires a sense of humour, a taste in sarcasm, a habit of
brevity — not by knobs, but by watching what those things *with Mal
specifically* look like, proposing patterns, and absorbing them on approval.
Persona evolution is gated; persona application is automatic.

### Layer 3 — Per-turn tone match

A fast classifier (`kaizen/persona/tone.py::classify_tone`) reads the last
~5 user messages and emits a `ToneTag`
(`terse | sarcastic | tired | playful | pissed | curious | neutral`). The
tag is injected into the prompt as a register hint — adjusts delivery, not
persona.

Default register is **slightly drier than Mal's average**. Asymmetric:
easier to warm up than to cool down. Persona never changes per-turn; only
the delivery does.

Heuristic implementation today; the function signature is the hook where a
local-model classifier plugs in later. Same pattern as `Curator.review`.

### Layer 4 — Voice canonicalization

Operator-facing speech comes from **one consistent tier** — not whichever
model the router happened to pick for the underlying reasoning. Small local
models do triage, classification, fact extraction, embedding, scribe bulk
work, draft thinking. The frontier (Claude through Max for Mal's personal
lane, per ADR 0006) handles speech.

If cost discipline forces local-tier voice in some flow, the pattern is:
local model thinks → frontier rewrites the final reply through the prior.
Costs little; smooths every seam.

The router-side hint lives at `kaizen/orchestration/budgets.py`
(`OPERATOR_VOICE_TIER`). The router consults it for any reply destined to
the operator surface.

## Why the four-layer model fixes the Dolphin test

| Failure mode in the Dolphin test | Fixed by |
|---|---|
| Flat, assistant-y tone | Layer 1 — explicit identity prior |
| No opinions, no defending positions | Layer 1 — prior mandates it |
| Didn't get better over time | Layer 2 — curator-gated learned voice |
| Didn't match Mal's energy (sarcasm, brevity) | Layer 3 — per-turn tone hint |
| Same model spoke and thought, with no character anchor | Layer 4 — voice canonicalization |
| No callbacks, no continuity | Memory (ADR 0002) — not in this ADR, but a prerequisite |

## Consequences

- **Persona is code + data, not a prompt.** Layer 1 lives in a file you
  review-edit. Layer 2 is learned and gated. Layers 3–4 are stateless
  computations.
- **The curator we already shipped is doing double duty** — it is the
  tools/skills authoring engine *and* the persona-evolution engine. Same
  gate, same approval flow.
- **Memory is a hard prerequisite** for the stack to feel "human." Layer 2
  needs the scribe to be wired (ADR 0002); the context engine needs to
  surface relevant past facts every turn. Without that substrate the
  layers compose but the agent has nothing to be *about*.
- **One model speaks.** The router cannot freely swap voice tiers based on
  cost alone; operator-facing replies are pinned to `OPERATOR_VOICE_TIER`.
  The router still freely routes everything else.

## Non-goals

- A `humor_level: 7` knob, or any persona-as-numeric-dial. Persona is
  learned from interaction, not tuned.
- A multi-persona system. There is one Kaizen.
- Emotional simulation. The prior explicitly forbids pretending to feelings
  it does not have.

## Related

- ADR 0002 — memory architecture (the substrate)
- ADR 0004 — headless core / sessions (the surface)
- ADR 0006 — model strategy (voice tier comes from here)
- `kaizen/curator/` — proposals → approved learned traits → prior
- `kaizen/safety/gate.py` — the gate every learned-trait change passes through
