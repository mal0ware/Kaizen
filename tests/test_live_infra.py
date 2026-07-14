"""Live infrastructure smoke tests — OPT-IN, real services required.

These are excluded from the default (mock-only) suite: each test skips unless
its env var is set. Run against the docker-compose stack:

    docker compose up -d
    KAIZEN_TEST_DATABASE_URL=postgresql+asyncpg://kaizen:kaizen@localhost:5432/kaizen \
    KAIZEN_TEST_REDIS_URL=redis://localhost:6379/0 \
    KAIZEN_TEST_CLAUDE_CODE=1 \
    pytest tests/test_live_infra.py -v

The pgvector test uses a deterministic bag-of-words embedder rather than
Ollama, so it verifies the real store (extension, schema, insert, cosine-
distance ordering) without a live embedding model. The Ollama embedding path
itself is exercised only when an Ollama server is up (not covered here).
"""
from __future__ import annotations

import os
import shutil

import pytest

from kaizen.memory.base import Fact

_DB_URL = os.environ.get("KAIZEN_TEST_DATABASE_URL")
_REDIS_URL = os.environ.get("KAIZEN_TEST_REDIS_URL")
_CLAUDE = os.environ.get("KAIZEN_TEST_CLAUDE_CODE")

EMBED_DIM = 768


class BagOfWordsEmbedder:
    """Deterministic 768-dim embedder: hashed bag-of-words, L2-normalised.

    Texts sharing words get closer cosine distance — enough to verify that
    pgvector really orders by similarity, with no model dependency.
    """

    async def embed(self, text: str) -> list[float]:
        vec = [0.0] * EMBED_DIM
        for token in text.lower().split():
            vec[hash(token) % EMBED_DIM] += 1.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]


@pytest.mark.skipif(not _DB_URL, reason="KAIZEN_TEST_DATABASE_URL not set")
async def test_postgres_pgvector_roundtrip_and_ordering():
    from sqlalchemy import text as sql_text

    from kaizen.memory.postgres import PostgresMemoryStore

    store = PostgresMemoryStore(_DB_URL, BagOfWordsEmbedder())
    await store.init_db()

    # Clean slate so ordering assertions are deterministic across runs.
    async with store._engine.begin() as conn:
        await conn.execute(sql_text("TRUNCATE facts"))

    await store.add_fact(Fact(subject="operator", attribute="favorite color", value="green"))
    await store.add_fact(Fact(subject="operator", attribute="editor", value="neovim btw"))
    await store.add_fact(Fact(subject="kaizen", attribute="deploy target", value="hetzner box"))

    results = await store.search("what is the operator favorite color", k=3)
    assert len(results) == 3
    assert results[0].attribute == "favorite color", (
        f"pgvector cosine ordering wrong: got {results[0]!r} first"
    )

    results = await store.search("where does kaizen deploy", k=1)
    assert results[0].value == "hetzner box"

    await store._engine.dispose()


@pytest.mark.skipif(not _REDIS_URL, reason="KAIZEN_TEST_REDIS_URL not set")
async def test_redis_ping_roundtrip():
    import redis.asyncio as aioredis

    client = aioredis.from_url(_REDIS_URL)
    try:
        assert await client.ping() is True
        await client.set("kaizen:smoke", "ok", ex=60)
        assert (await client.get("kaizen:smoke")) == b"ok"
    finally:
        await client.aclose()


@pytest.mark.skipif(not _CLAUDE, reason="KAIZEN_TEST_CLAUDE_CODE not set")
@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI not on PATH")
async def test_claude_code_provider_live():
    """One trivial live completion through the subscription lane (ADR 0008)."""
    from kaizen.core.models import Message, Role
    from kaizen.providers.base import CompletionRequest
    from kaizen.providers.claude_code import ClaudeCodeProvider

    provider = ClaudeCodeProvider()
    request = CompletionRequest(
        messages=[
            Message(role=Role.USER, content='Respond with exactly the word "ok" and nothing else.')
        ],
        max_tokens=32,
    )
    response = await provider.complete(request)
    assert response.text.strip(), "expected non-empty text from the claude CLI"
    assert "ok" in response.text.lower()
