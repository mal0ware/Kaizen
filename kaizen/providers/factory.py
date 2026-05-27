"""Build the model router from settings — wiring the billing/compute strategy.

Tier assignment (ADR 0008):
  - LOCAL  : Ollama (the home GPU) if `use_local_model`, else the provided
    fallback (mock for the offline dev path).
  - CHEAP  : metered Anthropic API key, if configured.
  - FRONTIER: Claude Code (subscription / the $200 plan) if enabled; else the
    metered API key; else falls back to whatever's available.

Heavy adapters are imported lazily, so a config that doesn't use them never
imports their deps. Nothing here is invoked until a request is routed.
"""
from __future__ import annotations

from kaizen.config import Settings
from kaizen.orchestration.router import Router
from kaizen.providers.base import Provider, Tier


def build_router(settings: Settings, fallback: Provider) -> Router:
    providers: dict[Tier, Provider] = {}

    if settings.use_local_model:
        from kaizen.providers.local import LocalProvider

        providers[Tier.LOCAL] = LocalProvider(settings.local_model, settings.local_model_endpoint)
    else:
        providers[Tier.LOCAL] = fallback

    if settings.anthropic_api_key:
        from kaizen.providers.anthropic import AnthropicProvider

        providers[Tier.CHEAP] = AnthropicProvider(
            settings.cheap_model, Tier.CHEAP, settings.anthropic_api_key
        )
        providers[Tier.FRONTIER] = AnthropicProvider(
            settings.frontier_model, Tier.FRONTIER, settings.anthropic_api_key
        )

    if settings.use_claude_code_auth:
        # Prefer the subscription ($200 plan) for the heavy/personal lane.
        from kaizen.providers.claude_code import ClaudeCodeProvider

        providers[Tier.FRONTIER] = ClaudeCodeProvider(Tier.FRONTIER)

    return Router(providers)
