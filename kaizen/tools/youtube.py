"""YouTube transcript tool — built around the lessons from the ytmerge project.

ytmerge failed in ways we must not repeat (ADR 0009):
  1. YouTube blocks transcript requests from datacenter IPs. -> This tool
     declares RunLocation.RESIDENTIAL so the orchestrator runs it from the home
     worker (a residential IP), never the cloud VPS.
  2. It swallowed block/rate-limit errors as "no captions." -> Here we classify:
     transient/blocked -> TransientToolError (retry/reroute); genuinely no
     captions -> a clear "no transcript" result; anything else -> bubble up.
  3. youtube-transcript-api is brittle (it broke 0.x -> 1.x). -> The dependency
     is hidden behind one swappable fetch function, and errors are classified by
     *type name* to stay robust across versions.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from kaizen.tools.base import RunLocation, TransientToolError

_VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})")

# Classify by exception *type name* (robust across library versions):
_TRANSIENT_NAMES = {
    "IpBlocked", "RequestBlocked", "TooManyRequests", "YouTubeRequestFailed", "AgeRestricted",
}
_NO_CAPTIONS_NAMES = {"TranscriptsDisabled", "NoTranscriptFound", "NoTranscriptAvailable"}


def extract_video_id(text: str) -> str | None:
    """Pull a YouTube video id from a URL or accept a bare 11-char id."""
    stripped = text.strip()
    match = _VIDEO_ID_RE.search(stripped)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", stripped):
        return stripped
    return None


def classify_error(exc: Exception) -> str:
    """Return 'transient', 'no_captions', or 'unknown' for a fetch exception."""
    name = type(exc).__name__
    if name in _TRANSIENT_NAMES:
        return "transient"
    if name in _NO_CAPTIONS_NAMES:
        return "no_captions"
    return "unknown"


def _fetch_segments(video_id: str) -> Any:
    """Swappable, isolated fetch — a library change touches only this function.

    Returns the optional library's native segment objects (each with a ``.text``
    attribute); typed ``Any`` because the dependency is lazy and version-fluid.
    """
    from youtube_transcript_api import YouTubeTranscriptApi  # lazy, optional dep

    return YouTubeTranscriptApi().fetch(video_id)


class YouTubeTranscriptTool:
    name = "youtube_transcript"
    description = "Fetch the transcript (captions) of a YouTube video by URL or id."
    run_location = RunLocation.RESIDENTIAL

    def __init__(self) -> None:
        # In-process cache; the real cache will live in the memory store (ADR 0002).
        self._cache: dict[str, str] = {}

    async def run(self, url: str = "", **kwargs: Any) -> str:
        video_id = extract_video_id(url)
        if not video_id:
            return "No YouTube video id found in the input."
        if video_id in self._cache:
            return self._cache[video_id]

        try:
            segments = await asyncio.to_thread(_fetch_segments, video_id)
        except Exception as exc:  # noqa: BLE001 — classified below
            kind = classify_error(exc)
            if kind == "transient":
                raise TransientToolError(
                    f"YouTube blocked/rate-limited ({type(exc).__name__}) for {video_id} — "
                    "retry or reroute to a residential worker."
                ) from exc
            if kind == "no_captions":
                return f"No transcript available for video {video_id} (captions disabled or none)."
            raise  # unknown -> surface as a real bug, not a fake 'no captions'

        text = " ".join(segment.text.replace("\n", " ") for segment in segments)
        self._cache[video_id] = text
        return text
