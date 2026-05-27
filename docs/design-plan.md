# Kaizen — Design Plan

A detailed, component-by-component plan: what each piece is, the method behind it, how it's structured, what it connects to, and the expected setup and result. **Deliberately not phased.** There's no "stage 1 → stage 2"; build order emerges from the work. Read these in any order — they describe a system, not a sequence. Decisions and their rationale live in the [ADRs](decisions/); this is the *how it works and fits* layer.

---

## Headless core & internal API

**Purpose.** The single always-on brain: the agent loop, session ownership, and the contract every surface talks to.

**Method.** A long-lived service runs the loop — assemble context → call the routed model → execute any tool calls → fold results back → repeat until done. It owns **session objects** (a conversation = a session with ordered turns) and exposes an **internal API** (send turn, stream response, attach to session, query state) that surfaces consume.

**Structure.** `kaizen/core/` — loop, context engine (assembles per-session history + retrieved memory, compresses when long), session store, the internal API contract.

**Connects to.** Everything: surfaces attach to it; orchestration/providers serve it; memory/identity feed its context; tools execute through it.

**Expected.** One process you can point any number of surfaces at; a conversation persists independent of any surface, so nothing is lost if a face disconnects.

## Surfaces (Discord, terminal, later web)

**Purpose.** The faces. Thin clients that carry input/output to and from the core — no logic of their own.

**Method.** Each surface authenticates to the core, opens/attaches to a session, streams turns. Because sessions live in the core, a thread can hand off between surfaces (Discord → terminal) and concurrent surfaces share one understanding.

**Structure.** `kaizen/surfaces/discord/` (a `discord.py` bot, own identity, shares Vixen's infra), `kaizen/surfaces/terminal/` (Rich for rendering, prompt_toolkit for input — the "pretty" Claude-Code-like CLI). Web later.

**Connects to.** The core's internal API only. Surfaces never touch models, memory, or tools directly.

**Expected.** Talk to Kaizen from anywhere; move a conversation between surfaces mid-thought; the terminal feels like a polished local app while the real work happens in the core.

## Orchestration & model router

**Purpose.** Decide *which brain* handles each unit of work, by cost and difficulty.

**Method.** Per request: a cheap **local triage** scores difficulty/stakes/urgency, then routes — Tier 0 local (free, high-volume), Tier 1 cheap cloud, Tier 2 frontier (rare/hard). Carries iteration and token **budgets** so cost can't run away. This is the same logic applied to latency (fast vs slow path) and to attention (respond vs absorb).

**Structure.** `kaizen/orchestration/` — router, triage classifier, budget guards, the local/cloud decision.

**Connects to.** Providers (executes the choice), real-time pipeline (fast/slow), cost discipline.

**Expected.** Hundreds of cheap tasks cost ~nothing; frontier models fire only when they earn it.

## Providers

**Purpose.** A uniform interface over every model backend so the loop never knows or cares which is in use.

**Method.** One adapter interface; concrete adapters for the Anthropic API, **Claude-Code auth** (to use the Max subscription for the operator's personal lane), and local engines (Ollama / LM Studio). Adding a backend never touches the loop.

**Structure.** `kaizen/providers/` — `base` interface + one module per backend.

**Connects to.** Orchestration (which picks), the worker pool (local backends may live on the home GPU).

**Expected.** Swap or add models by config; mix subscription, metered API, and local freely.

## Memory

**Purpose.** Know the operator and recall anything, by meaning, without forgetting to make room.

**Method.** Structured facts (`subject, attribute, value, confidence, source, first_seen, last_seen`) in Postgres; **semantic recall** via `pgvector` (a local embedding model vectorizes everything); **tiers** — hot (small distilled profile, always in context) → warm (everything, semantically searchable) → cold (summarized archive). A background **scribe** passively reads the streams, batches messages, and uses a cheap local model to extract candidate facts — learning is decoupled from talking to it.

**Structure.** `kaizen/memory/` — stores (Postgres/pgvector/Redis), fact model, tiering/summarization, the scribe worker, retrieval (RAG).

**Connects to.** The context engine (supplies recall), identity graph (shares the store), the scribe consumes surface streams.

**Expected.** Recall by meaning not keyword; a profile that sharpens over time; nothing truly lost. Memory is operator data — never committed to the repo.

## Identity & relationship graph

**Purpose.** Model people (present or absent), keep reputation separate from reality, and resolve who-is-who.

**Method.** Three kinds: **Entity** (a real person/thing, may be absent), **Account/handle** (an observed identity, linked to an entity with confidence, reversible), **Belief edge** (`observer → subject`, holding that observer's view). Objective facts on the entity; opinions on the observer's edge. A background **entity-resolution** job merges accounts (shared IDs, style embeddings, explicit cues) and refuses to merge on name alone.

**Structure.** `kaizen/identity/` — node/edge tables in Postgres + pgvector for similarity; the resolution job.

**Connects to.** Memory (shared store), surfaces (speaker attribution via platform IDs), real-time (knows who's talking).

**Expected.** A web that handles multiple accounts per person, two people one name, and discussed-but-absent characters — reputation as aggregate belief, never contaminating ground truth. (Operator asserts participant consent — full modeling permitted.)

## Curator (gated self-improvement)

**Purpose.** Let Kaizen get better at the operator's workflows — safely.

**Method.** A background pass reviews recent work and *proposes* new/updated skills, memory edits, and (eventually) code/design changes. Everything routes through an **approval gate** — it never self-applies. Skills move through active/stale/archive so they don't pile up.

**Structure.** `kaizen/curator/` — the review pass, the proposal queue, the gate.

**Connects to.** Skills, memory, and (for self-design) the docs in this repo as its working substrate.

**Expected.** It improves without drifting or acting unilaterally; the operator approves changes.

## Tools & skills

**Purpose.** Reach outside itself — search, transcripts, financial data, documents — and crystallize repeatable workflows.

**Method.** Tools are **Python** (I/O-bound; native buys nothing, and OpenBB is Python). Pattern: cheap/free fetch → local model digests/embeds → frontier reasons only when needed. Web search (Brave/Exa/Tavily/Firecrawl), YouTube (`youtube-transcript-api`), financial (OpenBB + market APIs + Hermes data), documents (fetch → parse → chunk → local embed → pgvector RAG). Skills are saved procedures the curator can author.

**Structure.** `kaizen/skills/` + a core-defined **tool interface** every tool implements. (The interface comes before the tools; tools plug into it.)

**Connects to.** The core (invokes tools in the loop), memory (RAG, ingested docs), Hermes integration (financial/data tools).

**Expected.** Add a capability by writing one module against the interface; fetching is cheap and ecosystem-rich.

## World-awareness & proactive initiation

**Purpose.** Track timelines and break silence when something genuinely matters.

**Method.** A background **world feed** (news/market/event streams) → a local **relevance model** scoring items against the operator's positions/projects/people → a **temporal model** tracking upcoming dated events and anticipating them → a high-bar **initiation policy** that may open a conversation when relevance+importance clear the bar. Ingestion and scoring are local; cloud only composes the message.

**Structure.** `kaizen/world/` (or within orchestration) — feed ingesters, relevance scorer, temporal index, initiation gate.

**Connects to.** Memory (what the operator cares about), real-time/interjection governor (same "only when it meaningfully contributes" discipline), Hermes (position-relevant events).

**Expected.** Silence is no barrier — it surfaces the right thing at the right time, without becoming noisy.

## Real-time response & interjection governor

**Purpose.** Contribute meaningfully at conversational pace, and know when to think longer.

**Method.** Per message: ingest (always) → cheap local triage (respond? how hard?) → **fast path** (quick local reply) or **slow path** (frontier + extended thinking, after verifying facts against memory; low confidence/conflict → think longer, search, or ask). A **latency budget** uses typing indicators/interim acks for long thinks. The **interjection governor**: triage is fast enough to *draft* an intervention, but in an active conversation Kaizen **re-checks the draft against the latest messages right before sending** — send only if it still meaningfully contributes; otherwise drop or revise. Plus social rules (don't interrupt human-to-human exchanges, cooldowns, back off when ignored, a talkativeness dial).

**Structure.** `kaizen/core/` (pipeline) + the governor; triage uses the local provider.

**Connects to.** Orchestration (tiering), memory (verification), identity (who's talking), world-awareness (proactive case).

**Expected.** In a fast 10-person channel it stays quiet unless it has something timely and on-point; high-stakes questions get verified, deliberate answers.

## Hermes integration

**Purpose.** Make the solo operator stronger around the trading platform — never a hand on the trigger.

**Method.** In-process/local-API (both Python). Roles: **observability** (ingest telemetry/fills/positions/risk/validation output; local model surfaces what matters), **journaling** (log decisions with rationale for later recall), **RiskAdvisory voice** (plain-language layer over Hermes's advise→discipline→vetoer gate), **adversarial analyst** (challenge theses, steelman the opposite, argue sizing, surface qualitative/event factors the quant model is blind to), **alerting** (DM on attention-worthy events). **Hard wall:** never executes trades, moves money, alters strategy params, or touches the validation gate (DSR ≥ 0.95). Advisor, not oracle.

**Structure.** `kaizen/integrations/hermes/` — telemetry ingest, journal, advisory/adversary prompts, alert rules. Strictly read-only toward Hermes execution.

**Connects to.** Memory (journal), world-awareness (position-relevant events), surfaces (alerts/Discord).

**Expected.** Better situational awareness, decision recall, and a tireless red-team — with zero capital risk because the wall is architectural.

## Deployment & compute topology

**Purpose.** Always-on presence, free local compute when available, never down.

**Method.** Always-on **core** on a Hetzner VPS (no GPU); the home desktop (RTX 3080 10GB) is an **on-demand GPU worker**; **Tailscale** links them privately; a **Pi wake relay** wakes the desktop on demand; cloud is the always-available floor and the heavy thinker. If the worker is asleep/waking, answer via cloud immediately and queue heavy local-eligible jobs. A **worker pool** generalizes: any machine running a worker can join (distribute jobs, not a single model's layers).

**Structure.** VPS: core + Discord + Postgres/pgvector/Redis. Home: GPU worker + Pi relay. See [ADR 0007](decisions/0007-compute-topology.md), [ADR 0013](decisions/0013-infrastructure-and-hardware.md).

**Expected.** The agent never depends on the desktop being on; local inference is a cost/privacy bonus when it is.

## Cost discipline

**Purpose.** Keep run-rate small and predictable.

**Method.** Local-first funnel (bulk at ~$0.50/M electricity) + tiered routing (Opus rare) + budget guards. Operator's personal lane uses Max via Claude-Code auth; autonomous/multi-user traffic uses metered API. See [ADR 0008](decisions/0008-cost-and-billing.md).

**Expected.** ~$55–120/mo disciplined; the Opus dial is the swing.

---

## How it all fits together

**An inbound Discord message.** Surface → core (attach to session) → ingested into memory (scribe, async) → triage (local) decides respond vs absorb → if respond, router picks a tier → context engine assembles session history + semantic recall + identity context → model responds (fast local or verified-slow frontier) → interjection governor re-checks relevance at send-time → surface delivers.

**A one-time history backfill.** Pull the server's history → embed locally on the 3080 (batched) → store in pgvector → tiered summaries compress the cold bulk. Now years of messages are searchable in milliseconds; the working set stays small.

**A proactive world event.** World feed ingests an item → local relevance scorer matches it to the operator's positions/people → temporal/initiation gate clears the bar → cloud composes a concise message → surface opens a conversation, even in silence.

**A Hermes moment.** Telemetry crosses a threshold (e.g., DSR ≥ 0.95, or a drawdown limit) → observability surfaces it → journal logs context → alert DMs the operator; if asked, the adversarial analyst challenges the thesis and surfaces blind spots — all read-only, with execution staying behind the wall.

## Setup & expected result

**Setup.** One-time-consent flow detects hardware, picks a local model size, installs Ollama, pulls a model, wires it up; the operator adds an Anthropic key and/or Claude-Code auth; the VPS runs the core + Discord; Tailscale + the Pi relay connect the home GPU; a backfill indexes existing history.

**Expected result.** An always-on agent you talk to from Discord or a terminal that knows you and the people around you, learns passively, watches the world and your positions, challenges your trading reasoning without ever touching execution, runs the cheap majority of its work for free on your own GPU, and gets better at you over time — at a disciplined, predictable cost.
