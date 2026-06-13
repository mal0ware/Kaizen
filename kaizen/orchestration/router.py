"""Triage + tiered routing.

`triage` scores a message's difficulty (a heuristic now; a local classifier
later — ADR 0005). It is the cost/quality lever of the whole system: a wrong
call either sends a hard question to a weak local model or burns frontier
dollars on a trivial one. The heuristic is graded against golden fixtures in
:mod:`kaizen.eval` so it can be tuned, and later swapped for a model, with the
behavior measured rather than guessed.

`Router` maps difficulty to a tier and falls back across available providers
(e.g., home GPU asleep -> cloud, or no cloud key -> local).
"""
from __future__ import annotations

import re
from enum import Enum

from kaizen.core.models import Message
from kaizen.providers.base import Provider, Tier


class Difficulty(int, Enum):
    EASY = 0
    MODERATE = 1
    HARD = 2


# Words that signal genuinely hard reasoning (analysis, design, judgement). Matched
# on whole-word boundaries so a casual "why not" or "explain it later" does not
# escalate — short messages carrying one of these are gated by a length floor below.
_HARD_HINTS = frozenset(
    {
        "analyze", "analyse", "design", "prove", "strategy", "tradeoff", "tradeoffs",
        "trade", "risk", "evaluate", "architect", "architecture",
    }
)

# Words that signal hard reasoning *only when the message is substantial enough*
# to be a real question rather than an aside. "why" / "explain" / "compare" are
# common in throwaway lines, so they require the length floor to fire HARD.
_SOFT_HARD_HINTS = frozenset(
    {"why", "explain", "compare", "unwind", "justify", "implications"}
)

# Verbs that signal a moderate synthesis / generation / planning ask — the kind
# of work the cheap tier handles. These pull a message up to MODERATE even when
# it is short and carries no hard hint.
_MODERATE_HINTS = frozenset(
    {
        "summarize", "summarise", "rewrite", "draft", "rephrase", "reword",
        "list", "recommend", "suggest", "compose", "outline", "translate",
        "difference", "differences", "help",
    }
)

# Below this length, a soft-hard hint (why/explain/...) is treated as an aside,
# not an analytical request. Real analysis questions clear this comfortably.
_SOFT_HARD_MIN_LEN = 40
# A long message is hard regardless of keywords — length alone implies substance.
_LONG_MESSAGE_LEN = 600
# A medium message with no other signal is at least MODERATE.
_MEDIUM_MESSAGE_LEN = 120

_WORD_RE = re.compile(r"[a-z]+")


def _words(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def triage(message: Message) -> Difficulty:
    """Score a message's difficulty for tier routing.

    Layered signals (highest wins):
      1. Long messages, or any whole-word hard hint -> HARD.
      2. A soft-hard hint (why/explain/...) -> HARD only past a length floor,
         so short asides don't over-route to the frontier tier.
      3. A moderate synthesis/generation verb, a medium-length message, or a
         multi-sentence question -> MODERATE.
      4. Otherwise EASY.
    """
    text = message.content
    length = len(text)
    words = _words(text)

    if length > _LONG_MESSAGE_LEN or (words & _HARD_HINTS):
        return Difficulty.HARD
    if (words & _SOFT_HARD_HINTS) and length >= _SOFT_HARD_MIN_LEN:
        return Difficulty.HARD

    if (words & _MODERATE_HINTS) and length >= _SOFT_HARD_MIN_LEN:
        return Difficulty.MODERATE
    if length > _MEDIUM_MESSAGE_LEN:
        return Difficulty.MODERATE
    # A multi-sentence message that asks something is at least moderate.
    if "?" in text and (text.count(".") + text.count("?")) >= 2:
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
