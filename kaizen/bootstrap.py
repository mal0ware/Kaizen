"""Build the one agent every surface attaches to.

Wires the core (router + memory + scribe) and the persona/learning stack
(curator + approval gate + proposal queue + skill registry + learned traits),
so it uses real providers/Postgres/ambient learning when configured and falls
back to mock + in-memory when nothing is set up — it always runs, infra or not.

Self-state (learned traits, graduated skills, active instincts, pending
proposals) rehydrates from the :class:`~kaizen.state.base.StateStore` — the
file-backed store by default, so approvals survive restarts with zero infra.

Lived in ``kaizen.cli.main`` originally; moved here so the CLI, the Discord
surface, and the headless service all share one wiring path.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kaizen.config import Settings, load_settings
from kaizen.core.context import ContextEngine
from kaizen.core.loop import AgentLoop
from kaizen.core.models import Session
from kaizen.curator import Curator, Instinct, ProposalQueue
from kaizen.memory.factory import build_memory
from kaizen.memory.inmemory import InMemoryStore
from kaizen.memory.scribe import Scribe
from kaizen.providers.base import Tier
from kaizen.providers.factory import build_router
from kaizen.providers.mock import MockProvider
from kaizen.safety import ApprovalGate
from kaizen.skills import SkillRegistry, load_skills_dir
from kaizen.state import StateStore, build_state
from kaizen.tools.base import ToolRegistry
from kaizen.tools.builtin import CurrentTimeTool, EchoTool


@dataclass(slots=True)
class AgentBundle:
    """Everything the CLI / surfaces need handles on. Built once at startup."""

    loop: AgentLoop
    session: Session
    gate: ApprovalGate
    queue: ProposalQueue
    skills: SkillRegistry
    learned_traits: list[str]
    instincts: list[Instinct]
    state: StateStore


def build_agent(settings: Settings | None = None) -> AgentBundle:
    settings = settings or load_settings()

    state = build_state(settings)
    memory = build_memory(settings, InMemoryStore())
    tools = ToolRegistry()
    tools.register(CurrentTimeTool())
    tools.register(EchoTool())

    router = build_router(settings, MockProvider())
    scribe = Scribe(router.providers[Tier.LOCAL], memory) if settings.enable_scribe else None

    # Persona + curator wiring (ADR 0014). `learned_traits` is shared by
    # reference: when the operator approves an instinct proposal, the
    # apply-handler appends to this list (and persists it) and the next
    # prompt picks it up. Both lists rehydrate from the state store.
    learned_traits: list[str] = state.load_traits()
    instincts: list[Instinct] = state.load_instincts()
    skills = SkillRegistry()
    # Seed with the bundled example skills if present (active by default).
    try:
        examples = Path(__file__).resolve().parent / "skills" / "examples"
        for skill in load_skills_dir(examples):
            skills.register(skill)
    except Exception:
        pass
    # Then layer on previously approved (curator-graduated) skills.
    for skill in state.load_skills():
        skills.register(skill)

    gate = ApprovalGate(state=state)
    queue = ProposalQueue(gate=gate)
    curator = Curator()

    context = ContextEngine(memory, learned_traits=learned_traits)

    loop = AgentLoop(router, context, tools, scribe=scribe, curator=curator, proposal_queue=queue)
    return AgentBundle(
        loop=loop,
        session=Session(surface="cli"),
        gate=gate,
        queue=queue,
        skills=skills,
        learned_traits=learned_traits,
        instincts=instincts,
        state=state,
    )
