"""Build the memory store from settings.

If DATABASE_URL is set, use the Postgres + pgvector store; otherwise fall back to
the in-memory store so the offline/dev path runs with no infra. Heavy deps are
imported lazily.

The embedder is selected by ``settings.embedder``: ``"ollama"`` (the default,
semantic recall on the home GPU) or ``"hash"`` (a deterministic, dependency-free
hashing-trick embedder that needs no model or network — used by the pgvector
integration test and any deployment without an Ollama endpoint).
"""
from __future__ import annotations

from kaizen.config import Settings
from kaizen.memory.base import MemoryStore


def build_memory(settings: Settings, fallback: MemoryStore) -> MemoryStore:
    if settings.database_url:
        from kaizen.memory.embedder import Embedder, HashEmbedder, OllamaEmbedder
        from kaizen.memory.postgres import PostgresMemoryStore

        embedder: Embedder
        if settings.embedder == "hash":
            embedder = HashEmbedder(settings.vector_dim)
        else:
            embedder = OllamaEmbedder(settings.embed_model, settings.local_model_endpoint)
        return PostgresMemoryStore(settings.database_url, embedder, settings.vector_dim)
    return fallback
