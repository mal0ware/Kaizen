"""Postgres + pgvector memory store (ADR 0002).

Implements the same MemoryStore interface as InMemoryStore, so swapping is just
config (set DATABASE_URL). Structured facts live in a table; semantic recall uses
pgvector cosine distance. Heavy deps (sqlalchemy, asyncpg, pgvector) are only
imported when this module is used — the factory imports it lazily.

NOTE: EMBED_DIM must match the embedding model's output dimension
(nomic-embed-text = 768). Changing the embed model means changing this and
running a migration. We use create_all for the initial schema; Alembic migrations
come in once the schema needs versioned changes against existing data.
"""
from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, String, select
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from kaizen.memory.base import Fact
from kaizen.memory.embedder import Embedder

EMBED_DIM = 768  # nomic-embed-text


class Base(DeclarativeBase):
    pass


class FactRow(Base):
    __tablename__ = "facts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String)
    attribute: Mapped[str] = mapped_column(String)
    value: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    source: Mapped[str] = mapped_column(String, default="observed")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM))


class PostgresMemoryStore:
    name = "postgres"

    def __init__(self, database_url: str, embedder: Embedder, dim: int = EMBED_DIM):
        self._engine = create_async_engine(database_url)
        self._session = async_sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)
        self._embedder = embedder
        self._dim = dim

    async def init_db(self) -> None:
        """Create the pgvector extension and tables. Idempotent."""
        async with self._engine.begin() as conn:
            await conn.execute(sql_text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)

    async def add_fact(self, fact: Fact) -> None:
        vector = await self._embedder.embed(f"{fact.subject} {fact.attribute} {fact.value}")
        async with self._session() as session:
            session.add(
                FactRow(
                    subject=fact.subject,
                    attribute=fact.attribute,
                    value=fact.value,
                    confidence=fact.confidence,
                    source=fact.source,
                    first_seen=fact.first_seen,
                    last_seen=fact.last_seen,
                    embedding=vector,
                )
            )
            await session.commit()

    async def search(self, query: str, k: int = 5) -> list[Fact]:
        vector = await self._embedder.embed(query)
        async with self._session() as session:
            stmt = select(FactRow).order_by(FactRow.embedding.cosine_distance(vector)).limit(k)
            rows = (await session.execute(stmt)).scalars().all()
        return [
            Fact(
                subject=r.subject,
                attribute=r.attribute,
                value=r.value,
                confidence=r.confidence,
                source=r.source,
                first_seen=r.first_seen,
                last_seen=r.last_seen,
            )
            for r in rows
        ]
