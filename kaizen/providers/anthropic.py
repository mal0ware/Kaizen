"""Anthropic provider (API key or Claude-Code subscription auth).

Structure only — to be implemented against the Anthropic SDK when keys/auth are
configured. The `anthropic` package is an optional dependency and is imported
lazily inside `complete()` so importing this module stays light. See ADR 0006,
ADR 0008.
"""
from __future__ import annotations

from kaizen.providers.base import CompletionRequest, CompletionResponse, Tier


class AnthropicProvider:
    def __init__(self, model: str, tier: Tier = Tier.FRONTIER, api_key: str | None = None):
        self.name = f"anthropic:{model}"
        self.tier = tier
        self.model = model
        self._api_key = api_key

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        raise NotImplementedError(
            "AnthropicProvider is a stub. `pip install kaizen[anthropic]`, then implement "
            "complete() to map CompletionRequest -> the Messages API (tools, extended "
            "thinking) and back into CompletionResponse."
        )
