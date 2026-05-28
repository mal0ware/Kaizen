"""Secret redaction for ingest paths.

Patterns adapted from common credential shapes — Anthropic / OpenAI
``sk-…``, GitHub ``ghp_…`` / ``github_pat_…``, AWS ``AKIA…``, ``Bearer``
tokens, and long opaque blobs. The scribe and identity graph run
:func:`redact` on incoming content so credentials never reach long-term
memory (design-plan §Memory, §Identity).

These are heuristics: we err toward over-redaction in the bulk-blob path
(``«redacted:opaque»``). False positives on a 60-char hex hash are
acceptable; a leaked API key is not.
"""
from __future__ import annotations

import re
from dataclasses import replace

from kaizen.core.models import Message

# Ordered: more specific patterns first so they win when they overlap with
# the catch-all "long opaque blob" rule at the bottom.
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Anthropic / OpenAI style API keys: sk-... (incl. sk-ant-...)
    (re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_\-]{20,}\b"), "openai-key"),
    # GitHub personal access tokens (classic + fine-grained)
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"), "github-token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b"), "github-token"),
    # Slack bot/user tokens
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "slack-token"),
    # Google API keys
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b"), "google-key"),
    # AWS access key ids
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "aws-key"),
    # Bearer tokens — capture the token portion, not the word "Bearer"
    (re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._\-]{16,})"), "bearer"),
    # Generic long opaque blob (last-resort): 32+ chars of base64/hex-ish soup.
    # Word-bounded so it doesn't eat normal prose.
    (re.compile(r"\b[A-Za-z0-9+/=_\-]{40,}\b"), "opaque"),
)


def redact(text: str) -> str:
    """Replace likely secrets in ``text`` with ``«redacted:KIND»`` markers."""
    if not text:
        return text
    redacted = text
    for pattern, kind in _PATTERNS:
        if kind == "bearer":
            redacted = pattern.sub(lambda m: f"{m.group(1)}«redacted:bearer»", redacted)
        else:
            redacted = pattern.sub(f"«redacted:{kind}»", redacted)
    return redacted


def scrub_message(msg: Message) -> Message:
    """Return a copy of ``msg`` with redacted content. Non-content fields
    (role, tool calls, ids, timestamps) are preserved as-is."""
    return replace(msg, content=redact(msg.content))
