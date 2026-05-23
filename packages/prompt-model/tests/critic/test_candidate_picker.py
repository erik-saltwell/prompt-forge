from prompt_model._candidate.candidate import Candidate
from prompt_model._critic.candidate_picker import pick_next
from prompt_model._prompt.nodes import Document


def _make(case_ids: list[int], *, tested: int = 0, in_flight: int = 0, sum_scores: float = 0.0) -> Candidate:
    c: Candidate = Candidate(prompt=Document(), case_ids=list(case_ids))
    c.tested_count = tested
    c.in_flight_tests = in_flight
    c.sum_of_scores = sum_scores
    return c


def test_returns_none_when_no_candidates() -> None:
    assert pick_next([], floor_size=1, exploration_bonus=1.0) is None


def test_returns_none_when_no_eligible_candidates() -> None:
    exhausted: Candidate = _make([], tested=3, sum_scores=2.0)
    assert pick_next([exhausted], floor_size=1, exploration_bonus=1.0) is None


def test_skips_candidates_with_no_cases() -> None:
    exhausted: Candidate = _make([], tested=3, sum_scores=2.0)
    fresh: Candidate = _make([1, 2])
    assert pick_next([exhausted, fresh], floor_size=1, exploration_bonus=1.0) is fresh


def test_prefers_untested_candidate_over_tested() -> None:
    tested: Candidate = _make([1], tested=2, sum_scores=2.0)
    untested: Candidate = _make([2])
    assert pick_next([tested, untested], floor_size=1, exploration_bonus=1.0) is untested


def test_returns_first_untested_when_multiple_untested() -> None:
    a: Candidate = _make([1])
    b: Candidate = _make([2])
    assert pick_next([a, b], floor_size=1, exploration_bonus=1.0) is a


def test_picks_higher_ucb_when_all_tested_equally() -> None:
    # Equal effective_pulls — higher mean wins.
    high: Candidate = _make([1], tested=2, sum_scores=1.8)  # mean 0.9
    low: Candidate = _make([2], tested=2, sum_scores=0.2)  # mean 0.1
    assert pick_next([high, low], floor_size=1, exploration_bonus=1.0) is high


def test_exploration_bonus_lifts_less_pulled_candidate() -> None:
    # Same mean, but the less-pulled candidate has a larger exploration term.
    well_pulled: Candidate = _make([1], tested=10, sum_scores=5.0)  # mean 0.5
    lightly_pulled: Candidate = _make([2], tested=2, sum_scores=1.0)  # mean 0.5
    assert pick_next([well_pulled, lightly_pulled], floor_size=1, exploration_bonus=1.0) is lightly_pulled


def test_in_flight_tests_count_as_effective_pulls() -> None:
    # `a` has nothing completed but 3 in-flight pulls -> not "untested" by the picker.
    # `b` is genuinely untested and should win the initialization phase.
    a: Candidate = _make([1], in_flight=3)
    b: Candidate = _make([2])
    assert pick_next([a, b], floor_size=1, exploration_bonus=1.0) is b
