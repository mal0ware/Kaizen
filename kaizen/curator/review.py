"""Curator review pass: session -> instinct proposals; instincts -> skill proposals.

A first-pass heuristic extractor runs locally and is fast; the real value comes
from an LLM-backed extractor plugging into the same shape (provider call goes
where :meth:`Curator._extract_from_message` is now).

Known limitation (deliberate, unresolved): clustering in :meth:`Curator.evolve`
groups by shared trigger keywords only. The planned upgrade is embedding cosine
similarity via the ``Embedder`` protocol (``kaizen.memory.embedder``), which
requires making ``evolve`` async and injecting an embedder — deferred until the
local embedding path (Ollama) is running in deployment. The surface is stable,
so the swap stays local to ``_cluster_by_keyword_overlap``.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from kaizen.core.models import Message, Role, Session
from kaizen.curator.instinct import Instinct, InstinctStatus
from kaizen.curator.proposals import Proposal
from kaizen.skills.base import Skill

# Patterns that signal a stated preference / correction worth capturing.
# Kept narrow on purpose — false positives become low-confidence pending
# proposals that the operator can drop in one click.
_PREFERENCE_PATTERNS = (
    re.compile(
        r"\bI (?:always|usually|prefer(?: to)?|like to) ([^.!?\n]+)",
        re.IGNORECASE,
    ),
    re.compile(r"\bI (?:never|don't|do not) (?:want|like) ([^.!?\n]+)", re.IGNORECASE),
    re.compile(r"\b(?:please )?(?:always|never|don't|stop) ([^.!?\n]+)", re.IGNORECASE),
)

_STOPWORDS = frozenset(
    {
        "the", "a", "an", "to", "of", "and", "or", "is", "are", "was", "were",
        "be", "been", "being", "this", "that", "these", "those", "it", "in",
        "on", "at", "for", "with", "as", "by", "from", "into", "about", "you",
        "your", "i", "me", "my", "we", "our", "they", "them",
    }
)


def _keywords(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]{3,}", text.lower())
    return {t for t in tokens if t not in _STOPWORDS}


@dataclass(slots=True)
class Curator:
    """Reviews sessions and emits proposals. Stateless across calls."""

    min_confidence: float = 0.3
    extracted_source: str = "session"

    async def review(self, session: Session) -> list[Proposal]:
        """Scan a session's user messages for repeated preferences/corrections.

        Returns one proposal per extracted instinct. Repetition across messages
        raises confidence (each extra hit adds 0.15, capped at 1.0).
        """
        hits: dict[str, _Hit] = {}
        for msg in session.messages:
            if msg.role is not Role.USER:
                continue
            for action in self._extract_from_message(msg):
                key = action.lower().strip()
                bucket = hits.get(key)
                if bucket is None:
                    hits[key] = _Hit(action=action, count=1, evidence=[msg.content])
                else:
                    bucket.count += 1
                    bucket.evidence.append(msg.content)

        proposals: list[Proposal] = []
        for hit in hits.values():
            confidence = min(1.0, 0.4 + 0.15 * (hit.count - 1))
            if confidence < self.min_confidence:
                continue
            instinct = Instinct(
                trigger=" ".join(sorted(_keywords(hit.action))[:4]) or hit.action[:40],
                action=hit.action,
                confidence=confidence,
                source=self.extracted_source,
                evidence=hit.evidence[:5],
            )
            proposals.append(
                Proposal(
                    kind="instinct",
                    payload=instinct,
                    rationale=(
                        f"Observed {hit.count} time(s) in this session as a stated preference."
                    ),
                    confidence=confidence,
                )
            )
        return proposals

    def evolve(self, instincts: list[Instinct]) -> list[Proposal]:
        """Cluster related high-confidence instincts into proposed skills.

        Trivial keyword-overlap clustering: two instincts share a cluster if
        they share any trigger keyword. Embedding-based similarity is the
        planned replacement — see the module docstring for why it's deferred.
        """
        active = [i for i in instincts if i.status is InstinctStatus.ACTIVE]
        clusters = _cluster_by_keyword_overlap(active)

        proposals: list[Proposal] = []
        for cluster in clusters:
            if len(cluster) < 2:
                continue
            confidence = sum(i.confidence for i in cluster) / len(cluster)
            shared = set.intersection(*(_keywords(i.trigger) for i in cluster))
            name = "-".join(sorted(shared)[:3]) or f"cluster-{len(cluster)}"
            body_lines = ["When this skill applies, the operator has shown they want to:"]
            body_lines += [f"- {i.action}" for i in cluster]
            skill = Skill(
                name=name,
                description=f"Operator preference cluster: {', '.join(sorted(shared)) or name}",
                body="\n".join(body_lines),
                source="curator",
            )
            proposals.append(
                Proposal(
                    kind="skill",
                    payload=skill,
                    rationale=f"Graduated from {len(cluster)} related active instincts.",
                    confidence=confidence,
                )
            )
        return proposals

    def _extract_from_message(self, msg: Message) -> list[str]:
        out: list[str] = []
        for pattern in _PREFERENCE_PATTERNS:
            for match in pattern.findall(msg.content):
                phrase = match.strip(" ,.;:")
                if phrase:
                    out.append(phrase)
        return out


@dataclass(slots=True)
class _Hit:
    action: str
    count: int
    evidence: list[str] = field(default_factory=list)


def _cluster_by_keyword_overlap(instincts: list[Instinct]) -> list[list[Instinct]]:
    """Union-find by shared trigger keyword (single-link clustering)."""
    parent: dict[int, int] = {i: i for i in range(len(instincts))}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    keyword_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx, inst in enumerate(instincts):
        for kw in _keywords(inst.trigger):
            keyword_to_indices[kw].append(idx)

    for indices in keyword_to_indices.values():
        for i in indices[1:]:
            union(indices[0], i)

    groups: dict[int, list[Instinct]] = defaultdict(list)
    for idx, inst in enumerate(instincts):
        groups[find(idx)].append(inst)
    return list(groups.values())
