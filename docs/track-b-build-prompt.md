# Track B build prompt — port ECC's best ideas into Kaizen's runtime

This file is a **ready-to-paste Claude Code prompt**. Open Claude Code in the Kaizen repo root and paste everything below the line. It builds the three modules where Kaizen is currently emptiest (`skills/`, `curator/`, `safety/`) using ECC's designs as reference — clean reimplementation, no source copied. It is phased; let it finish and verify each phase before the next.

---

You are working in the **Kaizen** repo (`/Users/macuser/githubstuff/Kaizen`), an always-on, self-improving personal AI agent. Your job is to implement three currently-stubbed modules — `kaizen/skills/`, `kaizen/curator/`, and `kaizen/safety/` — by adapting the best ideas from the ECC project (skills schema, instinct-based continuous learning, gated self-improvement, secret redaction). This is a **clean reimplementation**: study designs, copy no third-party source.

## Ground rules (read before writing any code)

1. **Research first.** Before writing anything, read these files and obey their conventions:
   - `kaizen/core/models.py` (dataclass style: `@dataclass(slots=True)`, `_now()`/`_uid()` helpers, `from __future__ import annotations`)
   - `kaizen/tools/base.py` (the `Protocol` + `runtime_checkable` interface + `Registry` pattern you will mirror)
   - `kaizen/memory/base.py` (the `Fact` model — your `Instinct` model mirrors its `confidence`/`source`/`first_seen`/`last_seen` shape)
   - `kaizen/tools/youtube.py` (how optional deps are lazily imported and isolated behind one function)
   - `kaizen/core/loop.py` (how the agent loop consumes registries)
   - `docs/decisions/0009-tooling-and-skills.md` (the skill interface intent)
   - `docs/decisions/0004-headless-core-and-surfaces.md` and `docs/design-plan.md` §Curator (gated self-improvement: propose → operator approves → never self-applies)
   - `docs/research/ecc-evaluation-and-integration.md` (why we're doing this and what NOT to take)
2. **Match house style exactly:** Python 3.12+, `from __future__ import annotations`, `@dataclass(slots=True)` for plain models (pydantic is available but the core favors plain dataclasses — follow what each neighbor file does), async throughout, ruff line-length 100, module docstrings that cite the relevant ADR.
3. **No new heavy dependencies.** pydantic/pydantic-settings are available. **Do not add PyYAML** — parse `SKILL.md` frontmatter with a tiny hand-rolled `key: value` parser, or `import yaml` lazily inside a try/except and fall back. No network, no DB for this work.
4. **In-memory backends only for now.** Mirror `kaizen/memory/inmemory.py`. Postgres/pgvector come later behind the same interface; do not build them.
5. **Respect Kaizen's constraints, hard:**
   - **Gated, never auto-applied.** The curator only *proposes*; nothing it produces takes effect without passing through the approval gate in `safety/`.
   - **Depth-first.** Do NOT import ECC's breadth (no fleet of 61 agents, no 12-language rule packs, no 246 bundled skills). Build the *mechanism*, seed 1–2 example skills only.
   - **Operator-scoped.** Learning/profiling defaults to the operator.
6. **Tests are mandatory** and follow `tests/` style: plain functions, `asyncio_mode=auto` (just write `async def test_...`), no heavy fixtures. Put new tests in `tests/`.
7. After each phase, run `python -m pytest -q`, `ruff check kaizen tests`, and `mypy kaizen` (best-effort). Do not call a phase done if tests fail.

## Phase 1 — `kaizen/skills/` (skill interface + SKILL.md schema)

Goal: a skill is a saved, reusable procedure the curator can author and the loop can surface — stored in an **ECC/Anthropic-compatible `SKILL.md` format** so the open skill ecosystem is ingestible later.

Build:
- `kaizen/skills/base.py`:
  - `@dataclass(slots=True) class Skill` with fields: `name: str`, `description: str` (the trigger/when-to-use text shown to the model), `body: str` (the procedure), `source: str = "authored"`, `status: SkillStatus = ACTIVE`, `created_at`, `last_used_at: datetime | None = None`.
  - `class SkillStatus(str, Enum)`: `ACTIVE`, `STALE`, `ARCHIVED` (the active/stale/archive lifecycle ADR 0009 wants).
  - `class SkillRegistry` mirroring `ToolRegistry`: `register`, `get`, `list`, and a `specs()` that returns model-facing `{name, description}` for active skills only.
- `kaizen/skills/loader.py`:
  - `parse_skill_md(text: str) -> Skill` — parse YAML-style frontmatter (`---` delimited, at minimum `name:` and `description:`) followed by a markdown body. **Important:** carry the full body through — do not drop content after the frontmatter (this was a real ECC bug; guard against it with a test).
  - `load_skills_dir(path) -> list[Skill]` — load every `*/SKILL.md` (or `*.md`) under a directory.
  - `to_skill_md(skill: Skill) -> str` — serialize back out (so the curator can persist authored skills).
- `kaizen/skills/__init__.py`: export the public surface; update the docstring (drop "Not yet implemented").
- Seed `skills/examples/search-first/SKILL.md` and `skills/examples/verification-loop/SKILL.md` (2 short example skills, ECC-inspired, in your own words) so loading is demonstrable.

Tests (`tests/test_skills.py`): round-trip parse↔serialize; **frontmatter-body-loss regression test** (a SKILL.md with multiple body sections survives intact); registry `specs()` excludes archived skills; `load_skills_dir` finds the seeded examples.

## Phase 2 — `kaizen/curator/` (instinct lifecycle + gated proposals)

Goal: a background pass that *proposes* improvements as confidence-scored "instincts," which graduate into skills only after the operator approves. Adapt ECC's `continuous-learning-v2` instinct model and `/evolve` clustering — your code, their shape.

Build:
- `kaizen/curator/instinct.py`:
  - `@dataclass(slots=True) class Instinct` mirroring `Fact`: `trigger: str`, `action: str`, `confidence: float = 0.5`, `source: str = "session"`, `status: InstinctStatus = PENDING`, `evidence: list[str]`, `first_seen`, `last_seen`.
  - `class InstinctStatus(str, Enum)`: `PENDING`, `ACTIVE`, `ARCHIVED`.
- `kaizen/curator/proposals.py`:
  - `@dataclass(slots=True) class Proposal`: `id`, `kind` (`Literal["skill","memory_edit","instinct"]`), `payload`, `rationale`, `confidence`, `status` (`PENDING`/`APPROVED`/`REJECTED`), `created_at`.
  - `class ProposalQueue`: `add`, `pending()`, `approve(id)`, `reject(id)`. Approval is the **only** path to effect; nothing here self-applies.
- `kaizen/curator/review.py`:
  - `class Curator` with an async `review(session) -> list[Proposal]` that scans a session's messages and emits candidate instincts/skill proposals (a simple heuristic extractor is fine for now — e.g. repeated user corrections, stated preferences; leave a clear hook where an LLM-backed extractor plugs in later via a provider).
  - `evolve(instincts: list[Instinct]) -> list[Proposal]` — cluster related high-confidence instincts into a proposed `Skill` (ECC's `/evolve`). Keep clustering trivial (group by shared trigger keywords); mark the real-similarity TODO.
- `kaizen/curator/__init__.py`: export, update docstring.

Tests (`tests/test_curator.py`): instinct confidence/status defaults; queue approve/reject transitions; `review` produces proposals from a crafted session; `evolve` turns a cluster of instincts into a skill proposal; **nothing becomes active without `approve`**.

## Phase 3 — `kaizen/safety/` (approval gate + redaction)

Goal: the gate that fronts every curator proposal and any write-capable action, plus secret redaction adapted from ECC's secret-detection patterns (guards the scribe/identity graph from ingesting credentials).

Build:
- `kaizen/safety/gate.py`:
  - `class ApprovalGate` with `submit(proposal) -> str` (queues for operator review), `pending()`, `approve(id)`, `reject(id)`, and a `requires_approval(action) -> bool` policy. The `curator.ProposalQueue` should route through this gate (compose, don't duplicate). Make it the single chokepoint.
- `kaizen/safety/redact.py`:
  - `redact(text: str) -> str` — mask common secret shapes (OpenAI `sk-...`, GitHub `ghp_...`/`github_pat_...`, AWS `AKIA...`, generic `Bearer <token>`, long hex/base64 blobs). Use compiled regexes; replace with `«redacted:KIND»`. (Patterns adapted from ECC/AgentShield, written fresh.)
  - `scrub_message(msg) -> Message` — return a redacted copy for safe ingestion.
- `kaizen/safety/__init__.py`: export, update docstring.

Tests (`tests/test_safety.py`): each secret pattern is masked; non-secret text is untouched; gate blocks until `approve`; a redacted message preserves non-secret content.

## Phase 4 — defaults & external audit (small)

- In `kaizen/orchestration/` budget guards / config, add ECC-derived **default constants** with comments: a thinking-token cap (~10k), an "earlier compaction" trigger, and a note that subagent-class work should prefer the cheap local tier. Don't restructure the router — it's already deeper than ECC.
- Add a short `docs/security/trust-model.md` (one page): "operator = Mal; the agent is trusted; here are the gates (approval gate, execution wall toward Hermes, redaction on ingest)." This is the cheapest security win per the upstream eval.
- In your final summary, tell me to run `npx ecc-agentshield scan` myself against the repo (it's an external Node tool; don't try to install or run it from here).

## Definition of done

- `kaizen/skills/`, `kaizen/curator/`, `kaizen/safety/` are implemented (no more "Not yet implemented" docstrings), wired so curator proposals flow through the safety gate, and the skill registry is loadable from `SKILL.md`.
- New tests pass; `ruff check` is clean; `mypy` best-effort clean.
- Nothing self-applies; no new heavy deps; no DB/network added; breadth not imported.
- End with a concise summary: what was built, the test count, and the manual follow-ups (AgentShield scan, wiring the curator into `core/loop.py`'s background pass, swapping in LLM-backed extraction later).

Work phase by phase. Show me the plan from Phase 0 (the files you read + what you'll build) before writing code.
