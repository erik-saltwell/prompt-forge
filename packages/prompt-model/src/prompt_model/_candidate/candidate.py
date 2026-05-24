from __future__ import annotations

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

    def __post_init__(self) -> None:
        random.shuffle(self.case_ids)

    def take_case_id(self) -> int:
        if not self.has_cases:
            msg = "Cannot take case when candidate has no cases"
            raise RuntimeError(msg)
        return self.case_ids.pop()

    @property
    def has_cases(self) -> bool:
        return bool(self.case_ids)

    @property
    def mean_score(self) -> float:
        if self.tested_count == 0:
            return 0.0
        return float(self.sum_of_scores) / float(self.tested_count)
