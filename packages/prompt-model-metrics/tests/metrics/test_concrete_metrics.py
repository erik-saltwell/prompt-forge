"""Tests for the concrete metrics.

Behaviors under test per metric:
  HallucinationMetric:  input (not ground_truth) appears in user prompt as context
  JsonCorrectnessMetric: valid JSON → score=1.0, no judge; invalid JSON → score=0.0, judge fires
"""

from __future__ import annotations

import asyncio

import pytest
from prompt_model._metrics.result import MetricResult
from prompt_model.config import LiteLLMConfig
from prompt_model_metrics import HallucinationMetric, JsonCorrectnessMetric

_CONFIG = LiteLLMConfig(model="fake/model")
_PROMPT_MD = "# Task\n\nDo the thing.\n"

_OK_RESULT = MetricResult(metric_name="placeholder", score=0.9, assessment="ok")


def _stub_acomplete(result: MetricResult = _OK_RESULT):
    async def _inner(system_prompt: str, user_prompt: str, config: LiteLLMConfig, *, response_format=None, log_name=None):
        return result

    return _inner


# ─────────────────────────────────────────────
# HallucinationMetric
# ─────────────────────────────────────────────


def test_hallucination_passes_input_as_context(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    async def _stub(system_prompt: str, user_prompt: str, config: LiteLLMConfig, *, response_format=None, log_name=None):
        captured.append(user_prompt)
        return _OK_RESULT

    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _stub)
    metric = HallucinationMetric(_CONFIG)
    asyncio.run(metric.evaluate(_PROMPT_MD, "source document text", "output text", None))
    assert "source document text" in captured[0]


def test_hallucination_does_not_require_ground_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _stub_acomplete())
    metric = HallucinationMetric(_CONFIG)
    # Should not raise even with ground_truth=None
    result: MetricResult = asyncio.run(metric.evaluate(_PROMPT_MD, "input", "output", None))
    assert isinstance(result, MetricResult)


def test_hallucination_ground_truth_not_used_as_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """ground_truth should not appear as the context block — input is the context."""
    captured: list[str] = []

    async def _stub(system_prompt: str, user_prompt: str, config: LiteLLMConfig, *, response_format=None, log_name=None):
        captured.append(user_prompt)
        return _OK_RESULT

    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _stub)
    metric = HallucinationMetric(_CONFIG)
    asyncio.run(metric.evaluate(_PROMPT_MD, "THE REAL CONTEXT", "output", "THIS IS GROUND TRUTH"))
    user_prompt = captured[0]
    # input appears before ground_truth; the context block should reference input
    assert "THE REAL CONTEXT" in user_prompt
    context_pos = user_prompt.find("THE REAL CONTEXT")
    gt_pos = user_prompt.find("THIS IS GROUND TRUTH")
    assert context_pos < gt_pos  # input context comes first, reinforcing it's the primary context


# ─────────────────────────────────────────────
# JsonCorrectnessMetric
# ─────────────────────────────────────────────


def test_json_correctness_valid_json_scores_one(monkeypatch: pytest.MonkeyPatch) -> None:
    judge_called: list[bool] = []

    async def _stub(*args, **kwargs):
        judge_called.append(True)
        return _OK_RESULT

    monkeypatch.setattr("prompt_model._metrics.hybrid_metric.acomplete", _stub)
    metric = JsonCorrectnessMetric(_CONFIG)
    result: MetricResult = asyncio.run(metric.evaluate(_PROMPT_MD, "input", '{"key": "value"}', None))
    assert result.score == 1.0
    assert judge_called == []  # judge must not be called on valid JSON


def test_json_correctness_invalid_json_scores_zero_and_calls_judge(monkeypatch: pytest.MonkeyPatch) -> None:
    from prompt_model._metrics.hybrid_metric import JudgeDiagnosis

    judge_called: list[bool] = []

    async def _stub(*args, response_format=None, **kwargs):
        judge_called.append(True)
        if response_format is JudgeDiagnosis:
            return JudgeDiagnosis(
                culprit_node_id="1.1",
                rationale="No format instruction",
                target_behavior="Output valid JSON",
                success_criterion="Output parses as JSON",
            )
        return _OK_RESULT

    monkeypatch.setattr("prompt_model._metrics.hybrid_metric.acomplete", _stub)
    metric = JsonCorrectnessMetric(_CONFIG)
    result: MetricResult = asyncio.run(metric.evaluate(_PROMPT_MD, "input", "not valid json {{{", None))
    assert result.score == 0.0
    assert judge_called  # judge must fire on invalid JSON
