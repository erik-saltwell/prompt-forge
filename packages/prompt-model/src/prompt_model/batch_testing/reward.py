import math
from typing import Protocol, runtime_checkable

from ..metrics import MetricResult


@runtime_checkable
class RewardStrategy(Protocol):
    """Collapse one pull's MetricResults into a single scalar reward in [0, 1] for UCB to consume."""

    def compute(self, results: list[MetricResult]) -> float: ...


class MeanReward:
    """Unweighted arithmetic mean of `.score` across all results."""

    def compute(self, results: list[MetricResult]) -> float:
        if not results:
            raise ValueError("MeanReward requires at least one MetricResult")
        return sum(r.score for r in results) / len(results)


class WorstReward:
    """`min(scores)`. Any single weak metric tanks the prompt."""

    def compute(self, results: list[MetricResult]) -> float:
        if not results:
            raise ValueError("WorstReward requires at least one MetricResult")
        return min(r.score for r in results)


class WeightedMeanReward:
    """Weighted mean of `.score` keyed by `metric_name`. Unknown metrics are ignored.

    Weights are normalized over the metrics actually present in the result list, so partial coverage
    still produces a value in [0, 1].
    """

    def __init__(self, weights: dict[str, float]) -> None:
        if any(w < 0 for w in weights.values()):
            raise ValueError("Weights must be non-negative")
        if not weights:
            raise ValueError("WeightedMeanReward requires at least one weight")
        self.weights: dict[str, float] = dict(weights)

    def compute(self, results: list[MetricResult]) -> float:
        applicable: list[tuple[float, float]] = [(self.weights[r.metric_name], r.score) for r in results if r.metric_name in self.weights]
        if not applicable:
            raise ValueError("No MetricResult matched any configured weight")
        total_weight: float = sum(w for w, _ in applicable)
        if total_weight == 0:
            raise ValueError("Total weight of matched metrics is zero")
        return sum(w * s for w, s in applicable) / total_weight


class SingleMetricReward:
    """Pick one metric's `.score` as the reward. Other metrics ride along for reporting only."""

    def __init__(self, metric_name: str) -> None:
        self.metric_name: str = metric_name

    def compute(self, results: list[MetricResult]) -> float:
        for r in results:
            if r.metric_name == self.metric_name:
                return r.score
        raise ValueError(f"No MetricResult with metric_name={self.metric_name!r} found")


class GeometricMeanReward:
    """Geometric mean of `.score`. Penalizes any low score harder than arithmetic mean.

    A zero score yields a reward of zero. Useful when "every metric should be decent" matters.
    """

    def compute(self, results: list[MetricResult]) -> float:
        if not results:
            raise ValueError("GeometricMeanReward requires at least one MetricResult")
        log_sum: float = 0.0
        for r in results:
            if r.score == 0.0:
                return 0.0
            log_sum += math.log(r.score)
        return math.exp(log_sum / len(results))
