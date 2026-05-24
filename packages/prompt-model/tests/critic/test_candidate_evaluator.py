from __future__ import annotations

import asyncio

import pytest
from prompt_model._critic.candidate_evaluator import evaluate_candidate
from prompt_model._critic.composite_scorer import MeanScorer
from prompt_model._critic.selection_data import _SelectionData
from prompt_model.config import LiteLLMConfig

from .conftest import FakeMetric, fake_acomplete_factory, make_candidate, make_cases, ok_result


def _patch_acomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("prompt_model._critic.candidate_evaluator.acomplete", fake_acomplete_factory())


def _cfg() -> LiteLLMConfig:
    return LiteLLMConfig(model="fake/model")


def test_happy_path_runs_metrics_and_records(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_acomplete(monkeypatch)
    sd: _SelectionData = _SelectionData(make_candidate("alpha", case_count=2))
    metric: FakeMetric = FakeMetric([ok_result(0.8)])

    asyncio.run(
        evaluate_candidate(
            selection_data=sd,
            inputs=make_cases(2),
            execution_config=_cfg(),
            metrics=[metric],  # type: ignore[list-item]
            scorer=MeanScorer(),
        )
    )

    assert sd.completed_tests_this_run == 1
    assert sd.sum_of_scores == pytest.approx(0.8)
    assert metric.calls == 1
    assert len(sd.candidate.case_ids) == 1


def test_rejects_empty_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_acomplete(monkeypatch)
    sd: _SelectionData = _SelectionData(make_candidate("a"))
    with pytest.raises(ValueError, match="at least one metric"):
        asyncio.run(
            evaluate_candidate(
                selection_data=sd,
                inputs=make_cases(1),
                execution_config=_cfg(),
                metrics=[],
                scorer=MeanScorer(),
            )
        )
    assert len(sd.candidate.case_ids) == 1


def test_rejects_when_no_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_acomplete(monkeypatch)
    cand = make_candidate("a", case_count=1)
    cand.case_ids.clear()
    sd: _SelectionData = _SelectionData(cand)
    metric: FakeMetric = FakeMetric([ok_result(1.0)])

    with pytest.raises(ValueError, match="untested inputs"):
        asyncio.run(
            evaluate_candidate(
                selection_data=sd,
                inputs=make_cases(1),
                execution_config=_cfg(),
                metrics=[metric],  # type: ignore[list-item]
                scorer=MeanScorer(),
            )
        )


def test_metric_failure_rolls_back_case(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_acomplete(monkeypatch)
    sd: _SelectionData = _SelectionData(make_candidate("a", case_count=2))
    metric: FakeMetric = FakeMetric([RuntimeError("boom")])

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(
            evaluate_candidate(
                selection_data=sd,
                inputs=make_cases(2),
                execution_config=_cfg(),
                metrics=[metric],  # type: ignore[list-item]
                scorer=MeanScorer(),
            )
        )

    assert sd.completed_tests_this_run == 0
    assert len(sd.candidate.case_ids) == 2


def test_metrics_run_together_and_average(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_acomplete(monkeypatch)
    sd: _SelectionData = _SelectionData(make_candidate("a", case_count=1))
    m1: FakeMetric = FakeMetric([ok_result(1.0, metric_name="m1")])
    m2: FakeMetric = FakeMetric([ok_result(0.0, metric_name="m2")])

    asyncio.run(
        evaluate_candidate(
            selection_data=sd,
            inputs=make_cases(1),
            execution_config=_cfg(),
            metrics=[m1, m2],  # type: ignore[list-item]
            scorer=MeanScorer(),
        )
    )

    assert sd.sum_of_scores == pytest.approx(0.5)
    assert len(sd.results) == 2
