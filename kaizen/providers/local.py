"""Local provider — talks to an OpenAI-compatible local engine (Ollama / LM Studio).

Runs on the home GPU worker (ADR 0007). Structure only for now; `complete()`
will POST to the local endpoint. Import stays light (no heavy deps).
"""
from __future__ import annotations

from kaizen.providers.base import CompletionRequest, CompletionResponse, Tier


class LocalProvider:
    def __init__(self, model: str, endpoint: str = "http://localhost:11434", tier: Tier = Tier.LOCAL):
        self.name = f"local:{model}"
        self.tier = tier
        self.model = model
        self.endpoint = endpoint

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        raise NotImplementedError(
            "LocalProvider is a stub. Implement complete() to call the OpenAI-compatible "
            "endpoint at self.endpoint (e.g., Ollama) and map the response back."
        )
