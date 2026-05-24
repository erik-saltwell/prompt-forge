from __future__ import annotations

from prompt_model._critic.candidate_picker import pick_next_ucb
from prompt_model._critic.selection_data import _SelectionData

from .conftest import make_candidate


def _selection(heading: str, case_count: int = 1, *, tested: int = 0, sum_scores: float = 0.0) -> _SelectionData:
    cand = make_candidate(heading, case_count=case_count)
    cand.tested_count = tested
    cand.sum_of_scores = sum_scores
    return _SelectionData(cand)


def test_returns_none_when_no_candidates() -> None:
    assert pick_next_ucb([], exploration_bonus=1.0) is None


def test_returns_none_when_no_completed_history() -> None:
    # UCB requires completed_tests > 0; floor must run first.
    fresh: _SelectionData = _selection("a")
    assert pick_next_ucb([fresh], exploration_bonus=1.0) is None


def test_skips_candidate_with_no_cases() -> None:
    exhausted: _SelectionData = _selection("x", case_count=1, tested=2, sum_scores=2.0)
    exhausted.candidate.case_ids.clear()
    eligible: _SelectionData = _selection("y", case_count=1, tested=2, sum_scores=1.0)

    assert pick_next_ucb([exhausted, eligible], exploration_bonus=1.0) is eligible


def test_picks_higher_mean_when_equally_pulled() -> None:
    high: _SelectionData = _selection("h", tested=2, sum_scores=1.8)  # mean 0.9
    low: _SelectionData = _selection("l", tested=2, sum_scores=0.2)  # mean 0.1
    assert pick_next_ucb([high, low], exploration_bonus=0.1) is high


def test_exploration_bonus_lifts_less_pulled() -> None:
    well_pulled: _SelectionData = _selection("w", tested=10, sum_scores=5.0)  # mean 0.5
    lightly_pulled: _SelectionData = _selection("l", tested=2, sum_scores=1.0)  # mean 0.5
    assert pick_next_ucb([well_pulled, lightly_pulled], exploration_bonus=1.0) is lightly_pulled
