from __future__ import annotations

import math
from dataclasses import dataclass, field

from .._candidate import Candidate
from .._metrics import MetricResult


@dataclass
class _SelectionData:
    """Overlay one selection pass on top of a candidate's existing evaluation history so UCB scores reflect all observed inputs."""

    candidate: Candidate
    _completed_tests: int = 0
    _sum_of_scores: float = 0.0
    current_case_id: int | None = None
    results: list[MetricResult] = field(default_factory=list)

    @property
    def completed_tests_this_run(self) -> int:
        return self._completed_tests

    @property
    def completed_tests(self) -> int:
        return self._completed_tests + self.candidate.tested_count

    @property
    def sum_of_scores(self) -> float:
        return self._sum_of_scores + self.candidate.sum_of_scores

    @property
    def mean_score(self) -> float:
        if self.completed_tests == 0:
            return 0.0
        return self.sum_of_scores / float(self.completed_tests)

    def ucb_score(self, exploration_bonus: float, total_tests: int) -> float:
        return self.mean_score + exploration_bonus * math.sqrt(2 * math.log(total_tests) / self.completed_tests)

    @property
    def has_cases(self) -> bool:
        return self.candidate.has_cases

    def start_evaluation(self) -> int:
        return self.candidate.case_ids.pop()

    def complete_evaluation(self, results: list[MetricResult], score: float) -> None:
        self._sum_of_scores += score
        self.results.extend(results)
        self._completed_tests += 1

    def rollback_evaluation(self, case_id: int) -> None:
        self.candidate.case_ids.insert(0, case_id)

    def integrate_results_into_candidate(self) -> None:
        self.candidate.tested_count = self.completed_tests
        self.candidate.sum_of_scores = self.sum_of_scores
        if self.results:
            self.candidate.results = self.results
