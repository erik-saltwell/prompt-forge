import math

import pytest
from prompt_model import MetricResult
from prompt_model._critic import GeometricScorer, MeanScorer, SingleMetricScorer, WeightedMeanScorer, WorstScorer


def _r(name: str, score: float) -> MetricResult:
    return MetricResult(metric_name=name, score=score, assessment="ok")


def test_mean_reward() -> None:
    assert MeanScorer().compute([_r("a", 0.4), _r("b", 0.8)]) == pytest.approx(0.6)


def test_mean_reward_empty_raises() -> None:
    with pytest.raises(ValueError):
        MeanScorer().compute([])


def test_worst_reward() -> None:
    assert WorstScorer().compute([_r("a", 0.9), _r("b", 0.1), _r("c", 0.5)]) == 0.1


def test_weighted_mean_reward_normalizes() -> None:
    strat: WeightedMeanScorer = WeightedMeanScorer({"a": 1.0, "b": 3.0})
    assert strat.compute([_r("a", 1.0), _r("b", 0.0)]) == pytest.approx(0.25)


def test_weighted_mean_reward_ignores_unknown_metric() -> None:
    strat: WeightedMeanScorer = WeightedMeanScorer({"a": 1.0})
    assert strat.compute([_r("a", 0.7), _r("unknown", 0.1)]) == pytest.approx(0.7)


def test_weighted_mean_reward_no_match_raises() -> None:
    strat: WeightedMeanScorer = WeightedMeanScorer({"a": 1.0})
    with pytest.raises(ValueError):
        strat.compute([_r("b", 0.5)])


def test_single_metric_reward_picks_named() -> None:
    strat: SingleMetricScorer = SingleMetricScorer("focus")
    assert strat.compute([_r("noise", 0.1), _r("focus", 0.6)]) == 0.6


def test_single_metric_reward_missing_raises() -> None:
    strat: SingleMetricScorer = SingleMetricScorer("focus")
    with pytest.raises(ValueError):
        strat.compute([_r("noise", 0.1)])


def test_geometric_mean_reward() -> None:
    strat: GeometricScorer = GeometricScorer()
    assert strat.compute([_r("a", 0.25), _r("b", 0.64)]) == pytest.approx(math.sqrt(0.25 * 0.64))


def test_geometric_mean_short_circuits_on_zero() -> None:
    assert GeometricScorer().compute([_r("a", 0.5), _r("b", 0.0)]) == 0.0
