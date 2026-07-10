"""Unit tests for the Socratic Tutor coded tools.

These exercise the deterministic logic the agents depend on, with no LLM key and
no running server required. Run from the project root:

    pytest tests/test_socratic_tutor.py -v
"""
import pytest

from coded_tools.socratic_tutor.answer_checker import AnswerChecker
from coded_tools.socratic_tutor.mastery_tracker import MasteryTracker


@pytest.fixture
def checker():
    return AnswerChecker()


@pytest.fixture
def tracker():
    return MasteryTracker()


# --------------------------------------------------------------------------- #
# answer_checker
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("problem, answer, expected", [
    ("3/4 + 1/6", "11/12", True),
    ("3/4 + 1/6", "5/6", False),
    ("1/2 + 1/2", "1", True),
    ("2/3 * 3/4", "1/2", True),
    ("solve 2*x + 3 = 7 for x", "x = 2", True),
    ("solve 2*x + 3 = 7 for x", "2", True),
    ("solve 2*x + 3 = 7 for x", "x = 3", False),
    ("solve x/2 = 5 for x", "10", True),
])
def test_answer_checker(checker, problem, answer, expected):
    result = checker.invoke({"problem": problem, "student_answer": answer}, {})
    assert result["correct"] is expected


def test_answer_checker_accepts_decimal(checker):
    result = checker.invoke({"problem": "3/4", "student_answer": "0.75"}, {})
    assert result["correct"] is True


def test_answer_checker_accepts_implicit_multiplication(checker):
    result = checker.invoke({"problem": "solve 2x = 8 for x", "student_answer": "x=4"}, {})
    assert result["correct"] is True


def test_answer_checker_reports_expected_on_bad_answer(checker):
    result = checker.invoke({"problem": "3/4 + 1/6", "student_answer": "oops"}, {})
    assert result["correct"] is False
    assert "expected" in result


# --------------------------------------------------------------------------- #
# mastery_tracker  (the score + examiner combination rule)
# --------------------------------------------------------------------------- #
def test_starts_learning(tracker):
    sly = {}
    out = tracker.invoke(
        {"concept": "fractions", "last_correct": True, "examiner_ready": False}, sly
    )
    assert out["status"] == "learning"
    assert out["difficulty"] == 1
    assert sly["mastery"]["fractions"]["asked"] == 1


def test_advances_when_both_signals_agree(tracker):
    """First correct answer with examiner_ready triggers advance via stateless
    detection (asked == 1). Verify it advances at least once."""
    sly = {}
    out = tracker.invoke(
        {"concept": "fractions", "last_correct": True, "examiner_ready": True}, sly
    )
    assert out["status"] == "advance"
    assert out["difficulty"] == 2


def test_examiner_can_veto_advance(tracker):
    sly = {}
    out = None
    for _ in range(4):  # objective signal is ready, but examiner says no
        out = tracker.invoke(
            {"concept": "fractions", "last_correct": True, "examiner_ready": False}, sly
        )
    assert out["status"] == "learning"
    assert out["difficulty"] == 1


def test_wrong_answer_resets_streak(tracker):
    sly = {}
    tracker.invoke({"concept": "fractions", "last_correct": True, "examiner_ready": True}, sly)
    out = tracker.invoke({"concept": "fractions", "last_correct": False, "examiner_ready": True}, sly)
    assert out["streak"] == 0


def test_reaches_mastery_across_all_levels(tracker):
    sly = {}
    status = "learning"
    for _ in range(40):  # perfect run with the examiner on board should top out
        out = tracker.invoke(
            {"concept": "fractions", "last_correct": True, "examiner_ready": True}, sly
        )
        status = out["status"]
        if status == "mastered":
            break
    assert status == "mastered"
    assert sly["mastery"]["fractions"]["difficulty"] == 3