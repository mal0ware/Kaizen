"""Embeddings — turn text into vectors for semantic memory (ADR 0002).

`OllamaEmbedder` calls the local Ollama embeddings endpoint, so embedding (a
high-volume operation) runs free on the home GPU. `httpx` is a lazy optional dep.
Swap in a different embedder by implementing the Embedder protocol.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class OllamaEmbedder:
    def __init__(self, model: str = "nomic-embed-text", endpoint: str = "http://localhost:11434"):
        self.model = model
        self.endpoint = endpoint.rstrip("/")

    async def embed(self, text: str) -> list[float]:
        import httpx  # lazy optional dep

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.endpoint}/api/embeddings", json={"model": self.model, "prompt": text}
            )
            resp.raise_for_status()
            embedding: list[float] = resp.json()["embedding"]
            return embedding
