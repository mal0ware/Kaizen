"""Run the triage eval from the command line: ``python -m kaizen.eval``.

Grades the current keyword heuristic against the golden case set and prints the
report. Exit code is non-zero if accuracy falls below the regression floor, so
this doubles as a local pre-commit check, not just a viewer.
"""
from __future__ import annotations

import sys

from kaizen.eval.cases import GOLDEN_CASES
from kaizen.eval.harness import evaluate
from kaizen.orchestration.router import triage

# Regression floor for the keyword heuristic on the full golden set. The
# adversarial cases pull this below 1.0 on purpose; raise it when a better
# triager lands. Kept in sync with tests/test_eval.py.
MIN_ACCURACY = 0.80


def main() -> int:
    report = evaluate(triage, GOLDEN_CASES)
    print(report.render())
    if report.accuracy < MIN_ACCURACY:
        print(
            f"\nFAIL: accuracy {report.accuracy:.0%} < floor {MIN_ACCURACY:.0%}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
