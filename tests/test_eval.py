"""Tests for the triage eval harness and the heuristic it grades.

Two layers:
  1. Harness mechanics — scoring, confusion matrix, precision/recall — verified
     against controlled stub triagers so the math is pinned independent of the
     real heuristic.
  2. The real heuristic — graded against the golden fixtures, with a regression
     floor and a few pinned routing behaviors the harness exists to protect.
"""
from __future__ import annotations

from kaizen.core.models import Message, Role
from kaizen.eval import GOLDEN_CASES, TriageCase, evaluate
from kaizen.eval.__main__ import MIN_ACCURACY
from kaizen.eval.harness import EvalReport
from kaizen.orchestration.router import Difficulty, triage


def _msg(text: str) -> Message:
    return Message(role=Role.USER, content=text)


# --- harness mechanics ------------------------------------------------------


def test_perfect_triager_scores_100() -> None:
    """A triager that returns each case's own label scores a clean sweep."""
    label_lookup = {c.text: c.expected for c in GOLDEN_CASES}
    report = evaluate(lambda m: label_lookup[m.content], GOLDEN_CASES)
    assert report.accuracy == 1.0
    assert report.fair_accuracy == 1.0
    assert report.failures() == []


def test_constant_triager_metrics() -> None:
    """A triager that always says EASY: accuracy = share of EASY cases, and the
    confusion matrix puts every prediction in the EASY column."""
    cases = (
        TriageCase("a", Difficulty.EASY),
        TriageCase("b", Difficulty.HARD),
        TriageCase("c", Difficulty.MODERATE),
        TriageCase("d", Difficulty.EASY),
    )
    report = evaluate(lambda m: Difficulty.EASY, cases)
    assert report.correct == 2
    assert report.accuracy == 0.5

    conf = report.confusion()
    # Every prediction landed in the EASY column.
    assert conf[(Difficulty.EASY, Difficulty.EASY)] == 2
    assert conf[(Difficulty.HARD, Difficulty.EASY)] == 1
    assert conf[(Difficulty.MODERATE, Difficulty.EASY)] == 1

    pr = report.precision_recall()
    # EASY: 2 true positives over 4 predicted-EASY -> P=0.5; over 2 actual-EASY -> R=1.0
    easy_p, easy_r = pr[Difficulty.EASY]
    assert easy_p == 0.5
    assert easy_r == 1.0
    # HARD never predicted -> precision denominator 0 -> defined as 0.0, recall 0.0
    hard_p, hard_r = pr[Difficulty.HARD]
    assert hard_p == 0.0
    assert hard_r == 0.0


def test_fair_accuracy_excludes_known_gaps() -> None:
    """fair_accuracy ignores cases flagged heuristic_misses; accuracy does not."""
    cases = (
        TriageCase("ok", Difficulty.EASY),  # graded both ways
        TriageCase("why not", Difficulty.EASY, heuristic_misses=True),  # excluded from fair
    )
    # Triager gets the non-flagged case right, the flagged one wrong.
    report = evaluate(
        lambda m: Difficulty.EASY if m.content == "ok" else Difficulty.HARD, cases
    )
    assert report.accuracy == 0.5  # 1 of 2 over all cases
    assert report.fair_accuracy == 1.0  # 1 of 1 over non-flagged cases


def test_empty_report_does_not_divide_by_zero() -> None:
    report = EvalReport(results=[])
    assert report.accuracy == 0.0
    assert report.fair_accuracy == 0.0


def test_render_is_nonempty_string() -> None:
    report = evaluate(triage, GOLDEN_CASES)
    text = report.render()
    assert "Triage eval:" in text
    assert "Confusion" in text


# --- golden set hygiene -----------------------------------------------------


def test_golden_set_covers_every_class() -> None:
    labels = {c.expected for c in GOLDEN_CASES}
    assert labels == set(Difficulty)


def test_golden_texts_are_unique() -> None:
    texts = [c.text for c in GOLDEN_CASES]
    assert len(texts) == len(set(texts))


# --- the real heuristic -----------------------------------------------------


def test_heuristic_clears_regression_floor() -> None:
    report = evaluate(triage, GOLDEN_CASES)
    assert report.accuracy >= MIN_ACCURACY, "\n" + report.render()


def test_heuristic_moderate_class_is_usable() -> None:
    """Regression guard for the defect the harness first surfaced: the old
    heuristic could not produce MODERATE for realistic messages (0% recall)."""
    report = evaluate(triage, GOLDEN_CASES)
    _, moderate_recall = report.precision_recall()[Difficulty.MODERATE]
    assert moderate_recall >= 0.5


def test_short_aside_with_soft_keyword_stays_easy() -> None:
    # 'why'/'explain' in a throwaway line must not escalate to the frontier tier.
    assert triage(_msg("why not")) is Difficulty.EASY
    assert triage(_msg("explain it later")) is Difficulty.EASY


def test_real_analysis_routes_hard() -> None:
    assert triage(_msg("Analyze the risk in this leveraged position.")) is Difficulty.HARD
    assert (
        triage(_msg("Walk me through how you'd unwind this position overnight."))
        is Difficulty.HARD
    )


def test_synthesis_ask_routes_moderate() -> None:
    assert (
        triage(_msg("Summarize the thread above into a short paragraph please."))
        is Difficulty.MODERATE
    )
    assert (
        triage(_msg("Rewrite this paragraph so it reads less stiff but keeps meaning."))
        is Difficulty.MODERATE
    )


def test_trivial_message_routes_easy() -> None:
    assert triage(_msg("hi")) is Difficulty.EASY
    assert triage(_msg("thanks!")) is Difficulty.EASY
