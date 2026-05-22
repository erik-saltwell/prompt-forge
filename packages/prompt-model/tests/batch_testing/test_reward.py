import math

import pytest
from prompt_model import MetricResult
from prompt_model._batch_testing import (
    GeometricMeanReward,
    MeanReward,
    SingleMetricReward,
    WeightedMeanReward,
    WorstReward,
)


def _r(name: str, score: float) -> MetricResult:
    return MetricResult(metric_name=name, score=score, assessment="ok")


def test_mean_reward() -> None:
    assert MeanReward().compute([_r("a", 0.4), _r("b", 0.8)]) == pytest.approx(0.6)


def test_mean_reward_empty_raises() -> None:
    with pytest.raises(ValueError):
        MeanReward().compute([])


def test_worst_reward() -> None:
    assert WorstReward().compute([_r("a", 0.9), _r("b", 0.1), _r("c", 0.5)]) == 0.1


def test_weighted_mean_reward_normalizes() -> None:
    strat: WeightedMeanReward = WeightedMeanReward({"a": 1.0, "b": 3.0})
    assert strat.compute([_r("a", 1.0), _r("b", 0.0)]) == pytest.approx(0.25)


def test_weighted_mean_reward_ignores_unknown_metric() -> None:
    strat: WeightedMeanReward = WeightedMeanReward({"a": 1.0})
    assert strat.compute([_r("a", 0.7), _r("unknown", 0.1)]) == pytest.approx(0.7)


def test_weighted_mean_reward_no_match_raises() -> None:
    strat: WeightedMeanReward = WeightedMeanReward({"a": 1.0})
    with pytest.raises(ValueError):
        strat.compute([_r("b", 0.5)])


def test_single_metric_reward_picks_named() -> None:
    strat: SingleMetricReward = SingleMetricReward("focus")
    assert strat.compute([_r("noise", 0.1), _r("focus", 0.6)]) == 0.6


def test_single_metric_reward_missing_raises() -> None:
    strat: SingleMetricReward = SingleMetricReward("focus")
    with pytest.raises(ValueError):
        strat.compute([_r("noise", 0.1)])


def test_geometric_mean_reward() -> None:
    strat: GeometricMeanReward = GeometricMeanReward()
    assert strat.compute([_r("a", 0.25), _r("b", 0.64)]) == pytest.approx(math.sqrt(0.25 * 0.64))


def test_geometric_mean_short_circuits_on_zero() -> None:
    assert GeometricMeanReward().compute([_r("a", 0.5), _r("b", 0.0)]) == 0.0
