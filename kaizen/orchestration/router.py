"""Triage + tiered routing.

`triage` scores a message's difficulty (a crude heuristic now; a local model
later — ADR 0005). `Router` maps difficulty to a tier and falls back across
available providers (e.g., home GPU asleep -> cloud, or no cloud key -> local).
"""
from __future__ import annotations

from enum import Enum

from kaizen.core.models import Message
from kaizen.providers.base import Provider, Tier


class Difficulty(int, Enum):
    EASY = 0
    MODERATE = 1
    HARD = 2


_HARD_HINTS = (
    "analyze", "analyse", "why", "design", "prove", "strategy",
    "trade", "risk", "explain", "compare", "evaluate",
)


def triage(message: Message) -> Difficulty:
    text = message.content.lower()
    if len(text) > 600 or any(hint in text for hint in _HARD_HINTS):
        return Difficulty.HARD
    if len(text) > 120:
        return Difficulty.MODERATE
    return Difficulty.EASY


_DIFFICULTY_TO_TIER = {
    Difficulty.EASY: Tier.LOCAL,
    Difficulty.MODERATE: Tier.CHEAP,
    Difficulty.HARD: Tier.FRONTIER,
}


class Router:
    def __init__(self, providers: dict[Tier, Provider]):
        if not providers:
            raise ValueError("Router needs at least one provider")
        self.providers = providers

    def choose(self, difficulty: Difficulty) -> Provider:
        target = _DIFFICULTY_TO_TIER[difficulty]
        # prefer the target tier, then fall back across whatever is available
        for tier in [target, *(t for t in Tier if t != target)]:
            if tier in self.providers:
                return self.providers[tier]
        raise RuntimeError("No providers configured")  # unreachable given __init__ guard
