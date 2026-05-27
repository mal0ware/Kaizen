"""Memory: structured facts + semantic recall + tiers + ambient scribe (ADR 0002).

Skeleton ships an in-memory store; the Postgres/pgvector/Redis implementation
drops in behind the same MemoryStore interface when infra exists.
"""
