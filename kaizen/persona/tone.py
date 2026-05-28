"""Per-turn tone classifier (ADR 0014, Layer 3).

Reads the most recent user messages and returns a :class:`ToneTag` that the
context engine injects into the prompt as a *register hint* — adjusts
delivery, not persona. Default register is slightly drier than the operator's
average; this asymmetry is enforced at the consumer side (the prompt
template), not here.

Today: a fast heuristic classifier good enough for routing hints. The
function signature is the hook for a local-model classifier (same pattern
as :meth:`kaizen.curator.review.Curator.review` — swap the implementation,
not the surface).
"""
from __future__ import annotations

import re
from enum import Enum

from kaizen.core.models import Message, Role

# Priority order (highest first) when multiple tags would match. Pissed wins
# over sarcastic because mis-reading anger as sarcasm is the worse failure.
_PRIORITY: tuple[str, ...] = (
    "pissed",
    "sarcastic",
    "tired",
    "playful",
    "curious",
    "terse",
    "neutral",
)


class ToneTag(str, Enum):
    TERSE = "terse"
    SARCASTIC = "sarcastic"
    TIRED = "tired"
    PLAYFUL = "playful"
    PISSED = "pissed"
    CURIOUS = "curious"
    NEUTRAL = "neutral"


_SARCASM_PHRASES = (
    "yeah right", "sure thing", "totally", "obviously", "of course",
    "/s", "as if", "shocking", "amazing,",
)
_TIRED_MARKERS = ("ugh", "tbh", "idk", "...", "..", "meh", "whatever")
_PLAYFUL_MARKERS = ("lol", "lmao", "lmfao", "haha", "hehe", "rofl")
_PISSED_MARKERS = (
    "wtf", "what the fuck", "fuck", "fucking", "stop", "shut up",
    "no.", "are you kidding", "are you serious",
)
_CURIOUS_OPENERS = ("why", "how come", "wonder", "explain", "what's the point")

_LATE_NIGHT_HOURS = frozenset({0, 1, 2, 3, 4, 5})


def _signals(text: str) -> set[str]:
    """Detect which signal classes fire on a single message."""
    if not text:
        return set()
    out: set[str] = set()
    lower = text.lower()

    # Pissed: caps, profanity, blunt-rejection forms.
    if any(m in lower for m in _PISSED_MARKERS):
        out.add("pissed")
    # All-caps words ≥ 3 letters (excluding common acronyms) suggest shouting.
    caps_words = re.findall(r"\b[A-Z]{3,}\b", text)
    if caps_words and len(caps_words) >= 2:
        out.add("pissed")

    # Sarcastic: explicit phrases, scare quotes, "..." after a flat statement.
    if any(p in lower for p in _SARCASM_PHRASES):
        out.add("sarcastic")
    if re.search(r'"[^"\n]{3,30}"', text) and "?" not in text:
        out.add("sarcastic")

    # Tired: explicit low-effort markers / ellipsis. Bare lowercase brevity
    # is *terse*, not tired — tiredness needs a specific signal.
    if any(m in lower for m in _TIRED_MARKERS):
        out.add("tired")

    # Playful: laughter, multiple exclamations, emoji-like sequences.
    if any(m in lower for m in _PLAYFUL_MARKERS):
        out.add("playful")
    if text.count("!") >= 2:
        out.add("playful")

    # Curious: open question forms.
    if any(lower.startswith(o) for o in _CURIOUS_OPENERS):
        out.add("curious")
    if "?" in text and "pissed" not in out:
        out.add("curious")

    # Terse: very short, no question, no laughter.
    if len(text) < 30 and "?" not in text and "playful" not in out:
        out.add("terse")

    return out


def classify_tone(messages: list[Message], window: int = 5) -> ToneTag:
    """Return the dominant tone tag across the last ``window`` user messages.

    Empty / no-user input → :attr:`ToneTag.NEUTRAL`.
    """
    recent_user = [m for m in messages[-window * 3 :] if m.role is Role.USER][-window:]
    if not recent_user:
        return ToneTag.NEUTRAL

    counts: dict[str, int] = dict.fromkeys(_PRIORITY, 0)
    for msg in recent_user:
        for sig in _signals(msg.content):
            counts[sig] = counts.get(sig, 0) + 1
        # Late-night bias: tired signal gets a bump when the message landed
        # between 00:00 and 05:59 UTC.
        if msg.created_at.hour in _LATE_NIGHT_HOURS:
            counts["tired"] = counts.get("tired", 0) + 1

    fired = [tag for tag, count in counts.items() if count > 0]
    if not fired:
        return ToneTag.NEUTRAL
    # Resolve by priority — first match in _PRIORITY among fired tags wins.
    for tag in _PRIORITY:
        if tag in fired:
            return ToneTag(tag)
    return ToneTag.NEUTRAL


_HINT_TEXT: dict[ToneTag, str] = {
    ToneTag.TERSE: "Match the operator's brevity. One or two sentences, no preamble.",
    ToneTag.SARCASTIC: (
        "Operator is being sarcastic. Return the sarcasm in kind; address the "
        "underlying skepticism, do not earnestly defend the target."
    ),
    ToneTag.TIRED: (
        "Operator is low-energy. Be brief, do not be perky, do not pile on "
        "options. One clear thing."
    ),
    ToneTag.PLAYFUL: "Operator is playful. Joke back. Stay dry — do not out-joke them.",
    ToneTag.PISSED: (
        "Operator is angry. Drop pleasantries; address the substance directly. "
        "If you were wrong, say so plainly. Do not over-apologise."
    ),
    ToneTag.CURIOUS: (
        "Operator is asking a real question. Answer it directly; cite evidence; "
        "say what you do not know."
    ),
    ToneTag.NEUTRAL: "",
}


def tone_hint(tag: ToneTag) -> str:
    """Return the register hint text for ``tag`` — empty for neutral."""
    return _HINT_TEXT[tag]
