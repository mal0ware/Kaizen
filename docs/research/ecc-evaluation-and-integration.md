# ECC vs Kaizen — Evaluation & Integration Roadmap

_Generated 2026-05-27 from a fresh clone of `affaan-m/ECC` (README + surface manifest) and the local Kaizen tree. Companion to [upstream-evaluation.md](upstream-evaluation.md), which compared Hermes Agent vs OpenClaw. This file answers a different question: **what, if anything, does ECC have that Kaizen should absorb — and how do we get that value into Kaizen, Hermes, and every repo we touch?**_

## TL;DR verdict

**ECC is not a competitor to Kaizen. It is a different category of thing, and the right move is to use it on two separate tracks.**

- **Track A — ECC as Claude Code tooling (literal install).** ECC is a config/skill/agent/hook bundle that rides *inside* an AI coding harness (Claude Code, Cursor, Codex, …). It makes *your coding sessions* more disciplined. This is directly useful for **building Kaizen and Hermes** and for a **global `~/.claude` setup** — but install it lean, not the full firehose. ECC's own README repeatedly warns that the full install bloats context and double-loads hooks.
- **Track B — ECC's patterns as Kaizen runtime design (conceptual port).** Kaizen is an always-on autonomous agent *runtime*; you don't "install ECC" into it. Instead you mine ECC's most-developed ideas — its **skills schema**, its **instinct-based continuous-learning loop**, and its **security scanner** — for Kaizen's *least*-developed modules (`skills/` doesn't exist yet, `curator/` is a 6-line stub, `safety/` is 4 lines). ECC is most valuable to Kaizen precisely where Kaizen is emptiest.

Do **not** import ECC's breadth (61 agents, 12-language rule packs, 246 skills). That is the same breadth trap Kaizen already rejected when it passed on forking OpenClaw. Stay depth-first.

## Why this isn't an apples-to-apples comparison

| | **ECC** (`affaan-m/ECC`) | **Kaizen** |
|---|---|---|
| What it *is* | A plugin/config bundle for AI coding harnesses | A standalone, always-on autonomous agent runtime |
| Has its own runtime? | **No** — borrows the host harness's loop | **Yes** — its own agent loop, service, surfaces |
| Primary user | A developer in a coding session | The operator, continuously, across life + trading |
| Lives where | `~/.claude/`, plugin dirs, per-repo config | A Hetzner VPS + home GPU worker |
| Core artifacts | SKILL.md files, agent prompts, hooks, rules, MCP configs | Python modules (loop, memory, identity, router, surfaces) |
| Memory | Flat files + a small SQLite state store, saved/restored by hooks | Postgres + pgvector + Redis, tiered, ambient scribe |
| Learning | "Instincts": confidence-scored patterns extracted from sessions, gated, `/evolve` into skills | `curator/` gated proposal loop (designed, not built) |
| Model economy | Config knobs (model routing, thinking-token caps, strategic compaction) | A real router: local triage → tiered local/cloud/frontier + budgets |
| Identity / people | None | First-class entity/account/belief graph |
| Distribution | `/plugin install ecc@ecc` or `install.sh` | `pip`/Docker service you run |
| Language | JS/TS + shell + Python (config-heavy) | Python (+ Rust/C++ hot paths later) |

The one-line way to hold it: **ECC makes Claude Code a better engineer; Kaizen *is* an agent.** The overlap is conceptual, in the few places where both need the same ideas (skills, self-improvement, safety gates, cost discipline).

## What ECC actually is (honest inventory)

Stripping the marketing, ECC ships seven kinds of artifact:

1. **Skills** (~246 `SKILL.md` files) — markdown workflow definitions with YAML frontmatter; the primary surface. Auto-suggested or invoked, reusable by agents and across harnesses. This is the most directly portable idea.
2. **Agents** (~61 subagent prompts) — scoped specialists (planner, code-reviewer, security-reviewer, per-language build-resolvers). Delegation targets.
3. **Hooks** (`hooks/hooks.json`) — fire on tool events (`SessionStart`, `PreToolUse`, `PostToolUse`, `Stop`). Used for memory save/restore between sessions, auto-format, secret-blocking, and pattern extraction.
4. **Rules** — always-on markdown guidelines (coding-style, git-workflow, testing, security, performance), organized `common/` + per-language. Plugins *can't* distribute these; they're copied manually into `~/.claude/rules/`.
5. **Continuous learning ("instincts")** — `continuous-learning-v2`: confidence-scored patterns extracted from your sessions, import/export, `/evolve` to cluster instincts into skills. Gated, not auto-applied.
6. **MCP configs** — curated server definitions (GitHub, Context7, Exa, Playwright, etc.).
7. **AgentShield** — a security scanner (`npx ecc-agentshield scan`) for CLAUDE.md/settings/MCP/hooks/agents: secrets, permission audit, hook-injection, MCP risk.

Plus a token-optimization philosophy (sonnet default, `MAX_THINKING_TOKENS` cap, earlier autocompact, haiku subagents) and a "research-first" discipline.

**Honesty flags** (don't take these at face value): the README's headline numbers — 182K→196K stars, "Anthropic Hackathon Winner," 207 contributors — are self-reported marketing. 196K stars would make it one of the most-starred repos on GitHub, which is extraordinary and worth independent verification before repeating. The *architecture and artifacts* are real and copyable regardless of whether the hype checks out. Treat ECC as a well-organized idea catalog, not gospel.

## The portable value — mapped to Kaizen modules

Ranked by leverage. The pattern: ECC is strongest exactly where Kaizen is emptiest.

### 1. Skills schema → Kaizen `skills/` (highest leverage)

- **Kaizen state:** the `skills/` directory **does not exist yet**. ADR 0009 promises a core-defined tool/skill interface "comes first," but it's unwritten. The `curator/` that's supposed to author skills is a 6-line `__init__.py`.
- **ECC offering:** a battle-tested `SKILL.md` format (markdown body + YAML frontmatter: name, description/trigger, body), proven to be loadable across three harnesses, plus ~246 concrete examples of what a good skill looks like.
- **The move:** adopt an `SKILL.md`-compatible schema for Kaizen's skill interface. Two payoffs — (a) the curator has a concrete artifact to *author into* and a lifecycle to manage (active/stale/archive, which ADR 0009 already wants); (b) Kaizen can ingest the open skill ecosystem (ECC's, Anthropic's official skills, others) as a *menu*, the same way the upstream eval treated OpenClaw's extension catalog. Borrow the format and a handful of relevant skills (search-first, verification-loop, security-review); don't vendor all 246.

### 2. Instinct loop → Kaizen `curator/` (high leverage)

- **Kaizen state:** `curator/` is designed (gated, propose→approve, never self-applies — design-plan §Curator) but unimplemented.
- **ECC offering:** `continuous-learning-v2` is a *working* instantiation of nearly the same spec — confidence-scored "instincts," a pending→promote lifecycle, import/export, and `/evolve` to graduate clusters of instincts into full skills. ECC's "gated, not auto-applied" is identical to your "propose → you approve" discipline.
- **The move:** model Kaizen's curator proposal queue on ECC's instinct lifecycle: each proposal carries a confidence score and provenance; low-confidence stays pending; the operator promotes; promoted clusters become skills (your curator + the skills schema above close the loop). This is the cleanest "borrow the design, write our own code" win — and it directly serves Kaizen's recursive self-design vision.

### 3. Security scanner + secret patterns → Kaizen `safety/` (medium-high, cheap)

- **Kaizen state:** `safety/` is a 4-line stub; redaction/sanitization/approval gates are designed but unwritten. The upstream eval already flagged "write a one-page Kaizen trust model" as the cheapest security win.
- **ECC offering:** AgentShield (secret detection across 14 patterns, permission audit, hook-injection analysis, MCP risk profiling) and concrete secret-detection regexes (`sk-`, `ghp_`, `AKIA…`) used in its `beforeSubmitPrompt` hook.
- **The move:** two things. (a) **Run AgentShield against Kaizen's own configs** (`.env.example`, `docker-compose.yml`, any MCP/agent config) as a free audit — it's `npx`, no install. (b) Lift its secret/redaction *patterns* into `kaizen/safety/redact.py` and `message_sanitization` — these guard the scribe and identity graph from ingesting credentials. Pair with the one-page trust model the upstream eval already recommended.

### 4. Cost/model knobs → Kaizen `orchestration/` (medium, confirmatory)

- **Kaizen state:** the router (triage → Tier 0 local / Tier 1 cheap cloud / Tier 2 frontier + budget guards) is architecturally *deeper* than ECC. Kaizen wins here.
- **ECC offering:** specific default values worth stealing — `MAX_THINKING_TOKENS: 10000`, earlier autocompact (`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE: 50`), haiku for subagents, and "strategic compact at logical breakpoints, not at 95%."
- **The move:** adopt these as *default constants* in the budget guards and `context_compressor`. ECC's "compact after research/milestone/debug, never mid-implementation" rule is a good heuristic for Kaizen's compression trigger. Confirmatory, not transformative.

### 5. Subagent prompts → Kaizen Hermes `adversarial analyst` (narrow)

- **Kaizen state:** deliberately single-brain, depth-first — no subagent fleet, by design. But the Hermes-integration "adversarial analyst" (challenge theses, steelman the opposite) *is* a red-team subagent in spirit.
- **ECC offering:** its `code-reviewer` / `security-reviewer` / adversarial agent prompts are decent source material for that one analyst's system prompt.
- **The move:** mine 2–3 agent prompts for phrasing when you write the adversarial analyst. Ignore the other 58.

### What flows the *other* way

Kaizen's memory (tiered Postgres/pgvector + ambient scribe) and its router are well beyond anything in ECC. There's nothing to import there — if anything, Kaizen is the more serious system on those axes. ECC's "memory persistence" is flat files restored by a hook; don't regress toward it.

## Track A — ECC as Claude Code tooling (global + Hermes + all repos)

This is what ECC is literally built for: making *your* coding sessions disciplined. It applies to building Kaizen, building Hermes, and every other repo — via one global install plus light per-repo config.

**Install once, globally, lean.** Use the minimal/core profile, not `--profile full`. From ECC's own warnings:

- Pick **one** path — plugin **or** manual installer. Never stack them (the #1 broken setup is `/plugin install` then `install.sh --profile full`, which double-loads hooks and duplicates skills).
- Recommended: `/plugin marketplace add https://github.com/affaan-m/ECC` then `/plugin install ecc@ecc`, **then manually copy only the rules you want** into `~/.claude/rules/ecc/` (`common/` + `python/` — that covers Kaizen and Hermes).
- If hooks feel too global, use the no-hooks path: `./install.sh --profile minimal --target claude` (excludes the hooks runtime), and add hooks later only if you want runtime enforcement.
- Keep **<10 MCPs and <80 tools** active per project (ECC's own context-budget guidance). Don't enable the full MCP set.

**Per repo (Kaizen, Hermes, others):** add a short `CLAUDE.md`/`AGENTS.md` describing that repo's stack and conventions, and rely on the global rules. Kaizen already has rich ADRs and a design-plan — point `CLAUDE.md` at those as the working substrate (which is literally Kaizen's own recursive-self-design vision, applied to the dev harness).

**The caution that matters for you specifically:** ECC is heavy and breadth-first; Kaizen and Hermes are deliberately depth-first. Installing all 246 skills + 61 agents + 12 language rule packs will bloat every session's context (ECC itself says this can shrink a 200K window toward ~70K) and contradicts the focus you chose. Cherry-pick: `common` + `python` rules, the `search-first` / `verification-loop` / `security-review` / `tdd-workflow` skills, and the `python-reviewer` agent. That's ~90% of the value at ~10% of the context cost.

## Track B — ECC's patterns into Kaizen's runtime

You do **not** install ECC into Kaizen. You implement Kaizen's stub modules using ECC's designs as reference (same "study the interface, copy no source" rule as the Hermes/OpenClaw eval). Concretely, in priority order:

1. **Define the skill interface + `SKILL.md` schema** (`kaizen/skills/`, plus the core tool/skill interface ADR 0009 wants). Make it `SKILL.md`-compatible so the open ecosystem is ingestible.
2. **Build the curator on the instinct lifecycle** (`kaizen/curator/`): confidence-scored proposals, pending→promote gate, evolve-into-skill. Wire it to the skill interface from step 1.
3. **Harden `kaizen/safety/`** with ECC-derived secret/redaction patterns; run AgentShield against Kaizen's configs; write the one-page trust model.
4. **Seed router/compressor defaults** from ECC's token knobs.
5. **Borrow phrasing** for the Hermes adversarial-analyst prompt.

Each is a place Kaizen is currently empty, and each respects Kaizen's stated constraints (gated, operator-scoped, depth-first).

## What to deliberately NOT take

- The 61-agent / 246-skill / 12-language **breadth** — the OpenClaw trap, already rejected.
- ECC's **hook-based flat-file memory** — strictly inferior to Kaizen's tiered store.
- The **cross-harness packaging machinery** (Cursor/Codex/Zed/Copilot adapters, install manifests) — irrelevant to a single-operator runtime.
- The **multi-`*` orchestration commands / PM2 / ccg-workflow runtime** — extra surface area, extra doors.
- The **marketing claims** — keep the discipline (research-first, gated learning, security audit), drop the star-count framing.

## Recommended sequence

1. **This week, free:** run `npx ecc-agentshield scan` against the Kaizen repo and the Hermes repo. Zero install, immediate signal.
2. **Global dev setup:** install ECC lean (plugin + `common`/`python` rules only), confirm no hook duplication, add a `CLAUDE.md` to Kaizen and Hermes.
3. **Kaizen runtime, step 1–2:** design the `SKILL.md`-compatible skill interface and the instinct-style curator queue (these unblock each other and are Kaizen's biggest current gaps).
4. **Kaizen runtime, step 3:** port secret/redaction patterns into `safety/`, write the trust model.
5. **Backfill defaults:** fold ECC's token knobs into the router/compressor.

## Provenance & method

ECC was read from its public README and surface manifest (clone not required for the design-level comparison; its artifacts are markdown/JSON config). Kaizen was read from the local tree: `README.md`, `docs/architecture.md`, `docs/design-plan.md`, ADRs 0001–0013, `docs/research/upstream-evaluation.md`, and the `kaizen/` package source (~1,570 LOC; core/providers/memory/tools partially built with 11 test files; `curator`, `safety`, `world`, and `skills` are stubs or absent). No third-party source is proposed for copying — same clean-reimplementation rule as the rest of Kaizen.
