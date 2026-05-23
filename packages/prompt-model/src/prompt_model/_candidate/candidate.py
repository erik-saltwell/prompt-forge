from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .._metrics import MetricResult
from .._prompt import Document


@dataclass
class Candidate:
    prompt: Document
    case_ids: list[int]

    results: list[MetricResult] = field(default_factory=list)
    sum_of_scores: float = 0.0
    tested_count: int = 0
    in_flight_tests: int = 0

    def __post_init__(self) -> None:
        random.shuffle(self.case_ids)

    def take_case_id(self) -> int:
        if not self.has_cases:
            msg = "Cannot take case when candidate has no cases"
            raise RuntimeError(msg)
        self.in_flight_tests += 1
        return self.case_ids.pop()

    def record_result(self, metric_results: list[MetricResult], reward: float) -> None:
        if self.in_flight_tests <= 0:
            msg = "Cannot record a result when no pulls are in flight"
            raise RuntimeError(msg)
        self.results.extend(metric_results)
        self.sum_of_scores += reward
        self.tested_count += 1
        self.in_flight_tests -= 1

    @property
    def has_cases(self) -> bool:
        return bool(self.case_ids)

    @property
    def effective_pulls(self) -> int:
        return self.tested_count + self.in_flight_tests

    @property
    def mean_score(self) -> float:
        return float(self.sum_of_scores) / float(self.effective_pulls)

    def ucb_score(self, exploration_bonus: float, total_tests: int) -> float:
        return self.mean_score + exploration_bonus * math.sqrt(2 * math.log(total_tests) / self.effective_pulls)

    def revert_case(self, case_id: int) -> None:
        self.in_flight_tests -= 1
        assert case_id not in self.case_ids
        self.case_ids.insert(0, case_id)

    def reset_for_ucb(self) -> None:
        pass
