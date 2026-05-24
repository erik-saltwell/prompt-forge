from __future__ import annotations

import math

from prompt_model._critic.selection_data import _SelectionData

from .conftest import make_candidate, ok_result


def test_initial_state_uses_candidate_baseline() -> None:
    cand = make_candidate("alpha", case_count=2)
    cand.tested_count = 4
    cand.sum_of_scores = 2.0
    sd: _SelectionData = _SelectionData(cand)

    assert sd.completed_tests_this_run == 0
    assert sd.completed_tests == 4
    assert sd.sum_of_scores == 2.0
    assert sd.mean_score == 0.5


def test_mean_score_zero_when_no_history() -> None:
    sd: _SelectionData = _SelectionData(make_candidate("x", case_count=1))
    assert sd.mean_score == 0.0


def test_complete_evaluation_accumulates_overlay() -> None:
    cand = make_candidate("a", case_count=3)
    cand.tested_count = 2
    cand.sum_of_scores = 1.0
    sd: _SelectionData = _SelectionData(cand)

    sd.complete_evaluation([ok_result(0.5)], 0.5)
    sd.complete_evaluation([ok_result(1.0)], 1.0)

    assert sd.completed_tests_this_run == 2
    assert sd.completed_tests == 4
    assert sd.sum_of_scores == 2.5
    assert sd.mean_score == 2.5 / 4


def test_rollback_returns_case_to_pool() -> None:
    cand = make_candidate("a", case_count=2)
    sd: _SelectionData = _SelectionData(cand)
    case_id: int = sd.start_evaluation()
    assert len(cand.case_ids) == 1

    sd.rollback_evaluation(case_id)
    assert len(cand.case_ids) == 2
    assert case_id in cand.case_ids


def test_integrate_writes_back_to_candidate() -> None:
    cand = make_candidate("a", case_count=2)
    cand.tested_count = 1
    cand.sum_of_scores = 0.5
    sd: _SelectionData = _SelectionData(cand)
    sd.complete_evaluation([ok_result(1.0)], 1.0)
    sd.complete_evaluation([ok_result(0.0)], 0.0)

    sd.integrate_results_into_candidate()

    assert cand.tested_count == 3
    assert cand.sum_of_scores == 1.5
    # results was empty pre-integration; new results replace by design (intentional per code review).
    assert len(cand.results) == 2


def test_ucb_score_formula() -> None:
    cand = make_candidate("a", case_count=2)
    cand.tested_count = 4
    cand.sum_of_scores = 2.0
    sd: _SelectionData = _SelectionData(cand)

    expected: float = 0.5 + 1.0 * math.sqrt(2 * math.log(10) / 4)
    assert sd.ucb_score(exploration_bonus=1.0, total_tests=10) == expected


def test_has_cases_delegates_to_candidate() -> None:
    cand = make_candidate("a", case_count=1)
    sd: _SelectionData = _SelectionData(cand)
    assert sd.has_cases is True

    sd.start_evaluation()
    assert sd.has_cases is False
