"""Golden fixtures for triage routing.

Each :class:`TriageCase` pairs a message with the difficulty tier a human
considers *correct* for it — the routing policy we want, independent of how any
particular triager happens to score it. Labels are the ground truth; the
heuristic is graded against them, not the other way around.

Difficulty policy (mirrors ADR 0005):

- ``EASY``     — greetings, acks, one-liners, simple lookups. Local tier.
- ``MODERATE`` — multi-sentence asks, light synthesis, short how-to. Cheap tier.
- ``HARD``     — analysis, design, trade/risk reasoning, multi-constraint
  problems, anything high-stakes. Frontier tier.

Cases are deliberately adversarial in places: some are written to expose the
current keyword heuristic's blind spots (e.g. a hard question with none of the
trigger words, or an easy message that happens to contain one). Those are marked
with ``heuristic_misses=True`` so the harness can report the heuristic's known
gaps without the fixture pretending the heuristic is perfect.
"""
from __future__ import annotations

from dataclasses import dataclass

from kaizen.orchestration.router import Difficulty


@dataclass(frozen=True, slots=True)
class TriageCase:
    """A labeled routing example.

    ``heuristic_misses`` documents whether today's keyword heuristic is expected
    to mis-route this case. It is metadata for reporting, not used to grade — the
    harness always grades against ``expected``.
    """

    text: str
    expected: Difficulty
    note: str = ""
    heuristic_misses: bool = False


GOLDEN_CASES: tuple[TriageCase, ...] = (
    # --- EASY: greetings, acks, trivial lookups --------------------------------
    TriageCase("hi", Difficulty.EASY, "bare greeting"),
    TriageCase("hey there", Difficulty.EASY, "greeting"),
    TriageCase("thanks!", Difficulty.EASY, "ack"),
    TriageCase("ok sounds good", Difficulty.EASY, "ack"),
    TriageCase("what time is it?", Difficulty.EASY, "trivial lookup"),
    TriageCase("ping", Difficulty.EASY, "one word"),
    TriageCase("yes do it", Difficulty.EASY, "short confirmation"),
    TriageCase("lol nice", Difficulty.EASY, "social"),
    TriageCase("got it, ttyl", Difficulty.EASY, "sign-off"),
    TriageCase("remind me to call mom", Difficulty.EASY, "simple imperative"),
    # --- MODERATE: multi-sentence asks, light synthesis ------------------------
    TriageCase(
        "Can you summarize the three messages above into a short paragraph for me?",
        Difficulty.MODERATE,
        "summarization request, moderate length",
    ),
    TriageCase(
        "What's the difference between a list and a tuple, and when should I reach "
        "for each one in day-to-day code?",
        Difficulty.MODERATE,
        "how-to / light synthesis",
    ),
    TriageCase(
        "Draft a two-line message to the team letting them know the deploy slipped "
        "to tomorrow and why.",
        Difficulty.MODERATE,
        "short generative task",
    ),
    TriageCase(
        "I have a meeting at 3 and another at 4:30, can you help me figure out when "
        "to grab lunch?",
        Difficulty.MODERATE,
        "light planning",
    ),
    TriageCase(
        "Rewrite this paragraph so it sounds less stiff but keeps the same meaning.",
        Difficulty.MODERATE,
        "rewrite",
    ),
    TriageCase(
        "List a few good restaurants near the office and say which is best for a "
        "quick lunch.",
        Difficulty.MODERATE,
        "recommendation",
    ),
    # --- HARD: analysis, design, trade/risk, multi-constraint ------------------
    TriageCase(
        "Analyze the risk in opening a leveraged position here given the earnings "
        "print tomorrow.",
        Difficulty.HARD,
        "explicit analyze + trade risk",
    ),
    TriageCase(
        "Design a memory architecture for an always-on agent that has to ingest "
        "millions of messages and still recall relevant facts fast.",
        Difficulty.HARD,
        "design problem",
    ),
    TriageCase(
        "Why does the router fall back across tiers instead of failing hard, and is "
        "that the right call?",
        Difficulty.HARD,
        "explanation + judgement",
    ),
    TriageCase(
        "Compare pgvector and a dedicated vector DB for this scale and tell me which "
        "you'd pick and why.",
        Difficulty.HARD,
        "compare + recommend",
    ),
    TriageCase(
        "Evaluate whether the curator should self-apply low-risk instincts or keep "
        "everything behind the approval gate.",
        Difficulty.HARD,
        "evaluate + policy",
    ),
    TriageCase(
        "Prove that the dedup logic in the proposal queue can't drop a higher-"
        "confidence proposal.",
        Difficulty.HARD,
        "prove",
    ),
    # --- Adversarial: hard intent, no trigger keywords (heuristic under-routes) -
    TriageCase(
        "Walk me through how you'd unwind this position if the trade goes against "
        "us overnight and the broker is down.",
        Difficulty.HARD,
        "hard reasoning, no analyze/why/design keyword",
        heuristic_misses=True,
    ),
    TriageCase(
        "Talk me through the tradeoffs of running the scribe inline versus in a "
        "background task.",
        Difficulty.HARD,
        "tradeoffs reasoning, no trigger keyword (short)",
        heuristic_misses=True,
    ),
    # --- Adversarial: easy intent, contains a trigger keyword (over-routes) -----
    TriageCase(
        "explain it later",
        Difficulty.EASY,
        "casual brush-off that contains 'explain'",
        heuristic_misses=True,
    ),
    TriageCase(
        "why not",
        Difficulty.EASY,
        "two-word agreement that contains 'why'",
        heuristic_misses=True,
    ),
)
