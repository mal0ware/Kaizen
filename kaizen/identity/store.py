"""In-memory identity graph for dev/test.

Entity resolution here is intentionally minimal (exact platform_id match). The
real store (Postgres + pgvector) adds style-embedding/cue-based, confidence-
scored, reversible resolution as a background job (ADR 0003).
"""
from __future__ import annotations

from kaizen.identity.models import Account, Belief, Entity


class IdentityGraph:
    def __init__(self) -> None:
        self.entities: dict[str, Entity] = {}
        self.accounts: dict[str, Account] = {}
        self.beliefs: list[Belief] = []

    def add_entity(self, entity: Entity) -> Entity:
        self.entities[entity.id] = entity
        return entity

    def add_account(self, account: Account) -> Account:
        self.accounts[account.id] = account
        return account

    def link(self, account: Account, entity: Entity, confidence: float = 1.0) -> None:
        account.entity_id = entity.id
        account.link_confidence = confidence

    def resolve(self, platform: str, platform_id: str) -> Entity | None:
        """Find the entity behind an observed account (exact id match for now)."""
        for account in self.accounts.values():
            if (
                account.platform == platform
                and account.platform_id == platform_id
                and account.entity_id
            ):
                return self.entities.get(account.entity_id)
        return None

    def record_belief(self, belief: Belief) -> Belief:
        self.beliefs.append(belief)
        return belief

    def reputation(self, subject_entity_id: str) -> list[Belief]:
        """All observers' beliefs about a subject — the aggregate reputation,
        kept separate from the subject entity's objective facts."""
        return [b for b in self.beliefs if b.subject_entity_id == subject_entity_id]
