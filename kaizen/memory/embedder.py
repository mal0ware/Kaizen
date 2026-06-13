"""Embeddings — turn text into vectors for semantic memory (ADR 0002).

`OllamaEmbedder` calls the local Ollama embeddings endpoint, so embedding (a
high-volume operation) runs free on the home GPU. `httpx` is a lazy optional dep.

`HashEmbedder` is a dependency-free, fully deterministic fallback: it maps text
to a fixed-dimension vector using the hashing trick (each token is hashed into a
bucket; buckets are L2-normalized). It needs no model download, no GPU, and no
network, so it makes the semantic-memory path runnable and *testable* offline —
the pgvector integration test uses it. Its recall is bag-of-words, not semantic,
but cosine distance over shared tokens is enough to prove the store round-trips
and ranks neighbors correctly.

Swap in a different embedder by implementing the Embedder protocol.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    async def embed(self, text: str) -> list[float]: ...


_TOKEN = re.compile(r"[a-z0-9]+")


class HashEmbedder:
    """Deterministic, offline embedder using the hashing trick.

    Tokenizes on word boundaries, hashes each token into one of ``dim`` buckets
    with a signed contribution, then L2-normalizes. Identical text always yields
    an identical vector; texts sharing tokens have a smaller cosine distance.
    No network, no model, no extra dependencies — purely a function of the input.
    """

    def __init__(self, dim: int = 768):
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN.findall(text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            h = int.from_bytes(digest, "big")
            bucket = h % self.dim
            sign = 1.0 if (h >> 63) & 1 else -1.0
            vec[bucket] += sign
        norm = math.sqrt(sum(component * component for component in vec))
        if norm == 0.0:
            # Empty / token-less text: a stable unit vector keeps cosine math defined.
            vec[0] = 1.0
            return vec
        return [component / norm for component in vec]

    async def embed(self, text: str) -> list[float]:
        return self._vector(text)


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
