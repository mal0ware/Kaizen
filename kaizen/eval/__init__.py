"""Evaluation harness for routing decisions.

Routing is the cost/quality lever of the whole system: every message is scored
by :func:`kaizen.orchestration.router.triage` and sent to a local, cheap, or
frontier tier accordingly. A wrong call is expensive in one of two ways —
under-routing sends a hard question to a weak local model (bad answer), and
over-routing burns frontier dollars on a trivial one.

Today ``triage`` is a keyword heuristic. The roadmap is to replace it with a
local classifier (ADR 0005). You cannot improve what you do not measure, so
this package provides:

- :mod:`kaizen.eval.cases` — golden, labeled fixtures (message -> expected tier).
- :mod:`kaizen.eval.harness` — scores any triager against a case set and reports
  accuracy + a confusion matrix, so the heuristic and any future model are
  compared on the same yardstick.

The harness takes a ``Triager`` callable, so swapping the heuristic for a
model-backed triager never touches the harness.
"""
from kaizen.eval.cases import GOLDEN_CASES, TriageCase
from kaizen.eval.harness import EvalReport, Triager, evaluate

__all__ = [
    "GOLDEN_CASES",
    "EvalReport",
    "TriageCase",
    "Triager",
    "evaluate",
]
