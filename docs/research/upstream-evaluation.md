# Kaizen — Harness Foundation: Hermes Agent vs OpenClaw

_Comparison generated 2026-05-26 from a fresh clone of both repos. **Note:** the decision later evolved from "fork Hermes Agent" to a **clean reimplementation** inspired by it (no source copied) — see [design-log](../design-log.md) and [ADR 0001](../decisions/0001-language-and-performance.md). This file remains the reference evaluation._

## TL;DR verdict

**Fork Hermes Agent. Use OpenClaw only as a reference catalog, not a base.**

Hermes Agent already *is* the Kaizen blueprint: a Python, MIT-licensed, model-agnostic harness whose core modules map almost 1:1 onto the things you said you wanted (local/cloud orchestration, a self-improving gated loop, agent-curated memory, a single gateway you talk to from Discord). It's leaner, it integrates in-process with your Python-heavy Hermes trading stack, and it ships an OpenClaw importer so you lose nothing by not forking OpenClaw.

OpenClaw is a ~15k-file TypeScript/Node monorepo with desktop companion apps and 135 extensions. Forking it means owning a huge surface area in a language your trading platform doesn't share. Its breadth is real, but breadth is exactly the thing you don't want for a personal, depth-first agent.

## Side-by-side

| | **Hermes Agent** (Nous) | **OpenClaw** |
|---|---|---|
| Language | Python (~1,900 .py) + TS for web/TUI | TypeScript/Node monorepo (~15k .ts/.js) |
| License | MIT | MIT |
| Clone size | ~121 MB | ~261 MB |
| Philosophy | Depth — self-improving, grows with *you* | Breadth — largest ecosystem, "does everything" |
| Extensions/plugins | Domain-organized skills + optional MCPs | 135 extensions + 58 skills + plugin SDK |
| Desktop apps | No (CLI + gateway + web dashboard) | Yes (macOS/iOS/Android/Win/Linux, auto-update) |
| Model routing | `providers/` + 6 adapters, `/model` swap | `model-catalog` + `provider-runtime` + extensions |
| Local model support | `lmstudio_reasoning.py`, auxiliary-model split | via provider extensions |
| Memory | Agent-curated MEMORY.md/USER.md, FTS5 session search, Honcho user-modeling | `src/memory` + `memory-host-sdk` |
| Self-improvement | `curator.py` + `background_review.py` (autonomous skill creation, periodic nudges) | Not a first-class loop |
| Channels | Telegram/Discord/Slack/WhatsApp/Signal/Email from one gateway | Similar channel set via extensions |
| Security track record | No reported CVEs as of May 2026 | Multiple CVEs historically; explicit trusted-operator trust model |
| Integrates with your Python Hermes | In-process (same language) | Cross-language (IPC/HTTP only) |

## What to KEEP from Hermes Agent (the core fork)

These modules in `agent/` are the parts worth building Kaizen on — several already do exactly what you described:

- **`conversation_loop.py`** — the agent loop itself. The spine.
- **`auxiliary_client.py`** — this is your local/cloud orchestration insight, *already built*: a primary model plus a cheaper auxiliary model for grunt work. Point the auxiliary at a local LM Studio/Ollama model and the primary at a frontier model — done.
- **`curator.py` + `background_review.py`** — the self-improving loop. Background review proposes skills/memory updates on a cadence; this is where you enforce **gated, not auto-applied** (propose → you approve), matching your advisory-discipline philosophy.
- **`memory_manager.py` + `memory_provider.py`** — agent-curated MEMORY.md/USER.md with size limits and nudges. Scope the deep user-profiling to *you* by default (the consent point — don't profile everyone in a shared Discord).
- **`context_engine.py` / `context_compressor.py` / `conversation_compression.py`** — context window management. Hard to get right; don't rebuild it.
- **`providers/base.py` + the adapter pattern** — clean multiprovider abstraction. Add your own adapters here if needed.
- **`iteration_budget.py` + `rate_limit_tracker.py`** — cost/loop-budget guards. Essential for an always-on VPS agent so it can't run away with tokens or spend.
- **`file_safety.py` + `redact.py` + `message_sanitization.py`** — safety/redaction primitives. Free hardening.
- **`gateway/`** — the single multi-channel process. For Kaizen, strip to **just the Discord channel** (your chosen interface) and ignore the rest until needed.

## What to BORROW from OpenClaw (reference only — don't fork)

- **The extension catalog** (`extensions/`, 135 of them) — use as a *menu* of which providers, channels, and tools exist and how they're wired. Great for "does anyone already integrate X?" lookups.
- **The formal plugin boundary** (`packages/plugin-sdk`, `plugin-package-contract`) — if Kaizen ever accepts third-party plugins, this contract pattern is worth studying. Not needed for a personal build.
- **The written trust/threat model** (`SECURITY.md` + their `trust` repo) — copy the *discipline*, not the code. They explicitly document "what is and isn't a security boundary." Given Kaizen will touch trading + home + Discord, writing a one-page Kaizen trust model ("operator = me; the agent is trusted; here are the gates") is the cheapest security win you can make.

## What to DROP / avoid

- The entire TS desktop-app layer (`apps/`, Sparkle auto-update) — irrelevant; Discord is your interface.
- The 135-extension breadth — that surface area is where OpenClaw's CVEs came from. Kaizen stays depth-first and scoped to you.
- Breadth-first "support everything" instinct in general. Every integration you add is a door.

## Recommended Kaizen path

1. **Fork Hermes Agent**, strip to the core: agent loop + memory + curator + providers + **Discord-only** gateway.
2. **Wire the orchestration** via `auxiliary_client` — local model (LM Studio/Ollama, e.g. a small Qwen/Gemma) for high-volume watching/parsing, frontier model for hard reasoning.
3. **Build the trading-ops layer as a skill/plugin** that talks to your Hermes platform. Same-language Python means you can import it directly or hit its API — start with read-only monitoring/journaling.
4. **Keep self-patching gated**: `background_review`/`curator` *propose* code/skill/memory changes; you approve. Never auto-merge to itself.
5. **Write a one-page Kaizen trust model** (borrowed discipline from OpenClaw) before it gets any write access to money, files, or home systems.
6. **Scope profiling to you** — the memory/user-model should build a picture of Mal, not silently dossier everyone in the Discord.

_Both repos are cloned in the sandbox at `/tmp/kaizen-research/{hermes-agent,openclaw}` for this session if you want to dig into specific files._
