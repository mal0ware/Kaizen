"""Build the memory store from settings.

If DATABASE_URL is set, use the Postgres + pgvector store (with the Ollama
embedder); otherwise fall back to the in-memory store so the offline/dev path
runs with no infra. Heavy deps are imported lazily.
"""
from __future__ import annotations

from kaizen.config import Settings
from kaizen.memory.base import MemoryStore


def build_memory(settings: Settings, fallback: MemoryStore) -> MemoryStore:
    if settings.database_url:
        from kaizen.memory.embedder import OllamaEmbedder
        from kaizen.memory.postgres import PostgresMemoryStore

        embedder = OllamaEmbedder(settings.embed_model, settings.local_model_endpoint)
        return PostgresMemoryStore(settings.database_url, embedder, settings.vector_dim)
    return fallback
