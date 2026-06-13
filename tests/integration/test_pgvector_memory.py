"""End-to-end pgvector memory test against a live Postgres (ADR 0002, REVIEW P1).

Runs only when ``KAIZEN_TEST_DATABASE_URL`` points at a reachable pgvector DB;
otherwise the whole package is skipped (see ``conftest.py``). Embeddings use the
deterministic, dependency-free ``HashEmbedder`` so the test needs no API key, no
model download, and no network — only the database.

What this proves:

* ``add_fact`` embeds and persists through SQLAlchemy + pgvector, and ``search``
  returns the cosine-nearest facts in rank order (the right neighbours come back).
* the ambient ``Scribe.observe`` write path stores extracted facts into the live
  store, and they are then retrievable by similarity — the "remembers without
  being taught" loop, proven against real infrastructure.
"""
from __future__ import annotations

import pytest

from kaizen.core.models import Message, Role, Session
from kaizen.memory.base import Fact
from kaizen.memory.postgres import PostgresMemoryStore
from kaizen.memory.scribe import Scribe
from kaizen.providers.base import CompletionRequest, CompletionResponse, Tier

pytestmark = pytest.mark.integration


async def test_add_and_similarity_search_returns_nearest(pg_store: PostgresMemoryStore) -> None:
    """Write N facts, query by similarity, assert the right neighbours rank first."""
    facts = [
        Fact(subject="user", attribute="builds", value="a black hole renderer in metal and vulkan"),
        Fact(subject="user", attribute="builds", value="a quant trading platform with risk gates"),
        Fact(subject="user", attribute="prefers", value="dark mode terminals and tiling windows"),
        Fact(subject="user", attribute="studies", value="graphics and gpu compute at university"),
        Fact(subject="user", attribute="enjoys", value="hiking remote alpine trails on weekends"),
    ]
    for fact in facts:
        await pg_store.add_fact(fact)

    # A query sharing the most tokens with the renderer fact should rank it first.
    results = await pg_store.search("black hole renderer metal vulkan", k=3)
    assert results, "similarity search returned nothing"
    assert results[0].value == "a black hole renderer in metal and vulkan"
    assert len(results) == 3  # k is honoured

    # A disjoint query domain surfaces the trading fact ahead of the renderer one.
    trading = await pg_store.search("quant trading risk platform", k=5)
    values = [f.value for f in trading]
    assert values[0] == "a quant trading platform with risk gates"
    assert (
        values.index("a quant trading platform with risk gates")
        < values.index("a black hole renderer in metal and vulkan")
    )


async def test_search_respects_k_limit(pg_store: PostgresMemoryStore) -> None:
    for i in range(7):
        await pg_store.add_fact(Fact(subject="user", attribute="note", value=f"note number {i}"))
    assert len(await pg_store.search("note", k=4)) == 4
    assert len(await pg_store.search("note", k=10)) == 7  # never more than stored


class _FactEmittingProvider:
    """Deterministic provider that returns a JSON fact array, exercising the real
    Scribe extraction → parse_facts → store path without a model or network."""

    name = "fact-emitter"
    tier = Tier.LOCAL

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            text=(
                '[{"subject":"user","attribute":"project","value":"singularity black hole renderer"},'
                '{"subject":"user","attribute":"role","value":"graphics and systems developer"}]'
            ),
            model="fact-emitter",
        )


async def test_ambient_scribe_write_path_persists_and_recalls(
    pg_store: PostgresMemoryStore,
) -> None:
    """The ambient scribe stores extracted facts in the live pgvector store, and
    they are then retrievable by similarity search."""
    scribe = Scribe(provider=_FactEmittingProvider(), memory=pg_store, min_new_user_msgs=1)
    session = Session(id="integration-session")
    session.add(Message(role=Role.USER, content="I'm building Singularity, a black hole renderer."))

    await scribe.observe(session)

    hits = await pg_store.search("singularity renderer project", k=3)
    assert any("singularity black hole renderer" in f.value for f in hits)
    assert all(f.source == "scribe" for f in hits)

    # Watermark advanced: a second observe with no new user turns is a no-op.
    before = len(await pg_store.search("graphics developer role", k=10))
    await scribe.observe(session)
    after = len(await pg_store.search("graphics developer role", k=10))
    assert before == after
