"""Interjection governor (ADR 0005).

Decides whether Kaizen should speak (vs absorb), and — crucially — re-checks a
drafted intervention against the latest messages *right before sending*, because
fast conversations move on while a draft is being composed. Heuristics here are
placeholders for a local relevance model.
"""
from __future__ import annotations

from dataclasses import dataclass

from kaizen.core.models import Message, Role


@dataclass(slots=True)
class GovernorConfig:
    talkativeness: float = 0.5  # 0 = quiet, 1 = chatty
    min_relevance: float = 0.3


def _relevance(text: str, context_text: str) -> float:
    """Fraction of the text's words that appear in the context. Placeholder for
    a semantic relevance score from a local model."""
    words = set(text.lower().split())
    if not words:
        return 0.0
    context = set(context_text.lower().split())
    return len(words & context) / len(words)


class InterjectionGovernor:
    def __init__(self, config: GovernorConfig | None = None):
        self.config = config or GovernorConfig()

    def should_respond(
        self, incoming: Message, recent: list[Message], addressed: bool = False
    ) -> bool:
        if addressed:
            return True
        if incoming.role != Role.USER:
            return False
        context = " ".join(m.content for m in recent)
        score = _relevance(incoming.content, context)
        # higher talkativeness lowers the bar
        threshold = max(self.config.min_relevance, (1.0 - self.config.talkativeness) * 0.5)
        return score >= threshold

    def still_relevant(self, draft: str, latest: list[Message]) -> bool:
        """Pre-send re-check: does the draft still meaningfully contribute given
        messages that arrived while it was being composed?"""
        if not latest:
            return True
        context = " ".join(m.content for m in latest)
        return _relevance(draft, context) >= self.config.min_relevance
