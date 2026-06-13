"""Scoring harness: grade a triager against a set of golden cases.

A ``Triager`` is anything that maps a :class:`~kaizen.core.models.Message` to a
:class:`~kaizen.orchestration.router.Difficulty` — the keyword heuristic today,
a local classifier tomorrow. :func:`evaluate` runs it over a case set and returns
an :class:`EvalReport` with overall accuracy, per-class precision/recall, and a
confusion matrix.

Two scores are reported on purpose:

- ``accuracy``        — fraction correct over *all* cases, including the ones
  marked ``heuristic_misses`` (the honest, full-set number).
- ``fair_accuracy``   — accuracy over cases *not* flagged as known heuristic
  blind spots, so the harness can distinguish "the heuristic is doing its job on
  the cases it claims to handle" from "the heuristic is fundamentally limited".

When a model-backed triager replaces the heuristic, watch ``accuracy`` climb
toward ``fair_accuracy`` and beyond — that delta is exactly the adversarial set
the heuristic can't reach.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from kaizen.core.models import Message, Role
from kaizen.eval.cases import TriageCase
from kaizen.orchestration.router import Difficulty

# A triager scores one message. Stable seam: the heuristic and any future
# model-backed classifier share this signature.
Triager = Callable[[Message], Difficulty]

_CLASSES: tuple[Difficulty, ...] = (Difficulty.EASY, Difficulty.MODERATE, Difficulty.HARD)


@dataclass(frozen=True, slots=True)
class CaseResult:
    case: TriageCase
    predicted: Difficulty

    @property
    def correct(self) -> bool:
        return self.predicted is self.case.expected


@dataclass(slots=True)
class EvalReport:
    results: list[CaseResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def correct(self) -> int:
        return sum(1 for r in self.results if r.correct)

    @property
    def accuracy(self) -> float:
        """Fraction correct over every case, blind spots included."""
        return self.correct / self.total if self.total else 0.0

    @property
    def fair_accuracy(self) -> float:
        """Accuracy excluding cases flagged as known heuristic blind spots."""
        fair = [r for r in self.results if not r.case.heuristic_misses]
        if not fair:
            return 0.0
        return sum(1 for r in fair if r.correct) / len(fair)

    def confusion(self) -> dict[tuple[Difficulty, Difficulty], int]:
        """``(expected, predicted) -> count``. Diagonal entries are correct."""
        counter: Counter[tuple[Difficulty, Difficulty]] = Counter()
        for r in self.results:
            counter[(r.case.expected, r.predicted)] += 1
        return dict(counter)

    def precision_recall(self) -> dict[Difficulty, tuple[float, float]]:
        """Per-class ``(precision, recall)``. Undefined denominators -> 0.0."""
        conf = self.confusion()
        out: dict[Difficulty, tuple[float, float]] = {}
        for cls in _CLASSES:
            tp = conf.get((cls, cls), 0)
            predicted_pos = sum(conf.get((e, cls), 0) for e in _CLASSES)
            actual_pos = sum(conf.get((cls, p), 0) for p in _CLASSES)
            precision = tp / predicted_pos if predicted_pos else 0.0
            recall = tp / actual_pos if actual_pos else 0.0
            out[cls] = (precision, recall)
        return out

    def failures(self) -> list[CaseResult]:
        return [r for r in self.results if not r.correct]

    def render(self) -> str:
        """Human-readable report — used by the CLI runner."""
        lines: list[str] = []
        lines.append(
            f"Triage eval: {self.correct}/{self.total} correct "
            f"(accuracy {self.accuracy:.0%}, fair {self.fair_accuracy:.0%})"
        )
        lines.append("")
        lines.append("Per-class precision / recall:")
        pr = self.precision_recall()
        for cls in _CLASSES:
            precision, recall = pr[cls]
            lines.append(f"  {cls.name:9s}  P={precision:.0%}  R={recall:.0%}")
        lines.append("")
        lines.append("Confusion (rows = expected, cols = predicted):")
        conf = self.confusion()
        header = "           " + "".join(f"{c.name:>9s}" for c in _CLASSES)
        lines.append(header)
        for expected in _CLASSES:
            row = f"  {expected.name:9s}" + "".join(
                f"{conf.get((expected, p), 0):>9d}" for p in _CLASSES
            )
            lines.append(row)
        failures = self.failures()
        if failures:
            lines.append("")
            lines.append(f"Misroutes ({len(failures)}):")
            for r in failures:
                flag = " [known heuristic gap]" if r.case.heuristic_misses else ""
                lines.append(
                    f"  expected {r.case.expected.name:9s} got {r.predicted.name:9s}"
                    f"  {r.case.text[:60]!r}{flag}"
                )
        return "\n".join(lines)


def evaluate(triager: Triager, cases: Sequence[TriageCase]) -> EvalReport:
    """Run ``triager`` over ``cases`` and return a scored :class:`EvalReport`."""
    results = [
        CaseResult(case=case, predicted=triager(Message(role=Role.USER, content=case.text)))
        for case in cases
    ]
    return EvalReport(results=results)
