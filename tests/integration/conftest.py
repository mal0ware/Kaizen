"""Fixtures for the live-infrastructure integration suite.

These tests run only when a pgvector Postgres is reachable. Point them at one
with the ``KAIZEN_TEST_DATABASE_URL`` env var, e.g.::

    KAIZEN_TEST_DATABASE_URL=postgresql+asyncpg://kaizen:kaizen@127.0.0.1:5433/kaizen

The repo ships a one-command bring-up that starts the container, creates the
``vector`` extension, and runs this suite — see ``scripts/pgvector-test.*`` and
the "Live pgvector integration test" section of the README.

When the env var is unset the whole package is skipped at collection time, so the
default offline suite stays green with no Postgres. We capture the URL at import
(module load) because the project-wide autouse ``_hermetic_settings`` fixture in
``tests/conftest.py`` strips ``KAIZEN_*`` from ``os.environ`` per test; capturing
here runs before any test-scoped teardown can remove it.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest

# Optional heavy deps: if the `db` extra is not installed, skip rather than error.
sqlalchemy = pytest.importorskip("sqlalchemy")
pytest.importorskip("asyncpg")
pytest.importorskip("pgvector")

from sqlalchemy import text as sql_text  # noqa: E402  (after importorskip guard)

from kaizen.memory.embedder import HashEmbedder  # noqa: E402
from kaizen.memory.postgres import EMBED_DIM, PostgresMemoryStore  # noqa: E402

TEST_DB_URL = os.environ.get("KAIZEN_TEST_DATABASE_URL")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip every test in this package when no live DB is configured.

    A module-level ``pytestmark`` only covers tests defined in that one module;
    this hook applies the skip to all items collected under ``tests/integration``,
    so the offline suite stays green with no Postgres present.
    """
    if TEST_DB_URL:
        return
    skip = pytest.mark.skip(
        reason="KAIZEN_TEST_DATABASE_URL not set; bring up pgvector and export it (see README)"
    )
    for item in items:
        if "tests/integration/" in item.nodeid or "tests\\integration\\" in item.nodeid:
            item.add_marker(skip)


@pytest.fixture
async def pg_store() -> AsyncIterator[PostgresMemoryStore]:
    """A PostgresMemoryStore backed by the live pgvector DB and the deterministic
    HashEmbedder (no API key, no model download, no network).

    Initializes the schema, truncates the facts table so each test starts from a
    known-empty state, and disposes the engine on teardown so the suite leaves no
    open connections behind.
    """
    assert TEST_DB_URL is not None  # narrowed by pytestmark skip
    store = PostgresMemoryStore(TEST_DB_URL, HashEmbedder(EMBED_DIM), dim=EMBED_DIM)
    await store.init_db()
    async with store._engine.begin() as conn:
        await conn.execute(sql_text("TRUNCATE TABLE facts RESTART IDENTITY"))
    try:
        yield store
    finally:
        await store._engine.dispose()
