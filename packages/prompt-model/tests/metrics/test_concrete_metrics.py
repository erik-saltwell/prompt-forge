"""Tests for the five concrete metrics.

Behaviors under test per metric:
  GEvalMetric:        criteria string appears in system prompt; returns valid MetricResult
  HallucinationMetric: input (not ground_truth) appears in user prompt as context
  CoverageMetric:      raises MissingGroundTruthError when ground_truth is None
  AlignmentMetric:     input is passed as reference source (not ground_truth)
  JsonCorrectnessMetric: valid JSON → score=1.0, no judge; invalid JSON → score=0.0, judge fires
"""

from __future__ import annotations

import asyncio

import pytest
from prompt_model._metrics.protocol import MissingGroundTruthError
from prompt_model._metrics.result import MetricResult
from prompt_model.config import LiteLLMConfig
from prompt_model.metrics.alignment import AlignmentMetric
from prompt_model.metrics.coverage import CoverageMetric
from prompt_model.metrics.g_eval import GEvalMetric
from prompt_model.metrics.hallucination import HallucinationMetric
from prompt_model.metrics.json_correctness import JsonCorrectnessMetric

_CONFIG = LiteLLMConfig(model="fake/model")
_PROMPT_MD = "# Task\n\nDo the thing.\n"

_OK_RESULT = MetricResult(metric_name="placeholder", score=0.9, assessment="ok")


def _stub_acomplete(result: MetricResult = _OK_RESULT):
    async def _inner(system_prompt: str, user_prompt: str, config: LiteLLMConfig, *, response_format=None, log_name=None):
        return result

    return _inner


# ─────────────────────────────────────────────
# GEvalMetric
# ─────────────────────────────────────────────


def test_g_eval_criteria_appears_in_system_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    async def _stub(system_prompt: str, user_prompt: str, config: LiteLLMConfig, *, response_format=None, log_name=None):
        captured.append(system_prompt)
        return _OK_RESULT

    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _stub)
    metric = GEvalMetric(_CONFIG, criteria="The output must be concise.")
    asyncio.run(metric.evaluate(_PROMPT_MD, "input", "output", None))
    assert "The output must be concise." in captured[0]


def test_g_eval_returns_valid_metric_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _stub_acomplete())
    metric = GEvalMetric(_CONFIG, criteria="Be helpful.")
    result: MetricResult = asyncio.run(metric.evaluate(_PROMPT_MD, "input", "output", None))
    assert isinstance(result, MetricResult)
    assert result.metric_name == metric.name


def test_g_eval_name_reflects_criteria(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each GEvalMetric instance has a distinct name derived from its criteria."""
    m1 = GEvalMetric(_CONFIG, criteria="Be concise.")
    m2 = GEvalMetric(_CONFIG, criteria="Be accurate.")
    assert m1.name != m2.name


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
# CoverageMetric
# ─────────────────────────────────────────────


def test_coverage_raises_when_ground_truth_is_none() -> None:
    metric = CoverageMetric(_CONFIG)
    with pytest.raises(MissingGroundTruthError):
        asyncio.run(metric.evaluate(_PROMPT_MD, "input", "output", None))


def test_coverage_uses_ground_truth_as_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_reference_prompts: list[str] = []

    class _TrackingCoverage(CoverageMetric):
        async def _extract_reference_points(self, input: str, ground_truth: str | None) -> list[str]:
            captured_reference_prompts.append(self.reference_extraction_prompt(input, ground_truth))
            return ["ref point"]

        async def _extract_claims(self, output: str) -> list[str]:
            return ["claim"]

        async def _generate_verdicts(self, claims, reference_points):
            from prompt_model._metrics.base_claim_metric import ClaimVerdict

            return [ClaimVerdict(claim="claim", passes=True)]

        async def _attribute_nodes(self, failing_verdicts, prompt_with_ids):
            return []

    metric = _TrackingCoverage(_CONFIG)
    asyncio.run(metric.evaluate(_PROMPT_MD, "some input", "some output", "THE REFERENCE"))
    assert any("THE REFERENCE" in p for p in captured_reference_prompts)


def test_coverage_fails_all_reference_points_when_output_has_no_claims() -> None:
    """With zero output claims but non-empty reference points, every key point should fail."""
    from prompt_model._metrics.base_claim_metric import ClaimVerdict, NodeAttribution

    class _EmptyOutputCoverage(CoverageMetric):
        async def _extract_claims(self, output: str) -> list[str]:
            return []

        async def _extract_reference_points(self, input: str, ground_truth: str | None) -> list[str]:
            return ["point A", "point B", "point C"]

        async def _generate_verdicts(self, claims: list[str], reference_points: list[str]) -> list[ClaimVerdict]:
            assert reference_points == ["point A", "point B", "point C"]
            assert claims == []
            # The verdict LLM is expected to emit one fail per reference point when the output is empty.
            return [ClaimVerdict(claim=rp, passes=False, reason="No output claim addresses this.") for rp in reference_points]

        async def _attribute_nodes(self, failing_verdicts: list[ClaimVerdict], prompt_with_ids: str) -> list[NodeAttribution]:
            return [NodeAttribution(claim=v.claim, culprit_node_id="document") for v in failing_verdicts]

    metric = _EmptyOutputCoverage(_CONFIG)
    result: MetricResult = asyncio.run(metric.evaluate(_PROMPT_MD, "input", "", "ref"))
    assert result.score == 0.0
    assert len(result.signals) == 3


def test_coverage_skips_verdict_call_when_no_reference_points() -> None:
    """Inverted from alignment: coverage should short-circuit on empty reference points, not empty claims."""
    from prompt_model._metrics.base_claim_metric import ClaimVerdict

    verdict_call_count: list[int] = [0]

    class _NoRefCoverage(CoverageMetric):
        async def _extract_claims(self, output: str) -> list[str]:
            return ["claim 1", "claim 2"]

        async def _extract_reference_points(self, input: str, ground_truth: str | None) -> list[str]:
            return []

        async def _generate_verdicts(self, claims, reference_points):
            verdict_call_count[0] += 1
            # Should never be invoked because _should_run_verdicts returns False on empty reference_points.
            return [ClaimVerdict(claim="X", passes=True)]

        async def _attribute_nodes(self, failing_verdicts, prompt_with_ids):
            return []

    # Directly exercise the gate.
    metric = _NoRefCoverage(_CONFIG)
    assert metric._should_run_verdicts(["claim"], []) is False
    assert metric._should_run_verdicts([], ["ref"]) is True


def test_coverage_signal_carries_completeness_framing() -> None:
    """Coverage's IssueSignal should describe missing key points, not unsupported assertions."""
    from prompt_model._metrics.base_claim_metric import ClaimVerdict, NodeAttribution
    from prompt_model._metrics.result import IssueSignal

    class _OneMissCoverage(CoverageMetric):
        async def _extract_claims(self, output: str) -> list[str]:
            return ["irrelevant claim"]

        async def _extract_reference_points(self, input: str, ground_truth: str | None) -> list[str]:
            return ["The funding round closed at $40M from Sequoia."]

        async def _generate_verdicts(self, claims, reference_points):
            return [
                ClaimVerdict(
                    claim="The funding round closed at $40M from Sequoia.",
                    passes=False,
                    reason="No output claim mentions the $40M amount or Sequoia.",
                )
            ]

        async def _attribute_nodes(self, failing_verdicts, prompt_with_ids):
            return [NodeAttribution(claim=v.claim, culprit_node_id="1.1") for v in failing_verdicts]

    metric = _OneMissCoverage(_CONFIG)
    result: MetricResult = asyncio.run(metric.evaluate(_PROMPT_MD, "source text", "the candidate summary text", "reference summary"))
    assert len(result.signals) == 1
    signal: IssueSignal = result.signals[0]
    assert signal.culprit_node_id == "1.1"
    assert "Missing key point" in signal.rationale
    assert "$40M" in signal.rationale
    assert "cover every key point" in signal.target_behavior
    assert "reference key point is addressed" in signal.success_criterion
    # output_snippet must be a verbatim slice of `output`, never the reference key point.
    assert signal.output_snippet == "the candidate summary text"
    # input_snippet sources from ground_truth for coverage (the reference), not the input.
    assert "reference summary" in signal.input_snippet


def test_coverage_assessment_uses_completeness_vocabulary() -> None:
    from prompt_model._metrics.base_claim_metric import ClaimVerdict, NodeAttribution

    class _MixedCoverage(CoverageMetric):
        async def _extract_claims(self, output):
            return ["c1"]

        async def _extract_reference_points(self, input, ground_truth):
            return ["ref1", "ref2", "ref3"]

        async def _generate_verdicts(self, claims, reference_points):
            return [
                ClaimVerdict(claim="ref1", passes=True),
                ClaimVerdict(claim="ref2", passes=True),
                ClaimVerdict(claim="ref3", passes=False, reason="missing"),
            ]

        async def _attribute_nodes(self, failing_verdicts, prompt_with_ids):
            return [NodeAttribution(claim="ref3", culprit_node_id="1.1")]

    metric = _MixedCoverage(_CONFIG)
    result: MetricResult = asyncio.run(metric.evaluate(_PROMPT_MD, "i", "o", "gt"))
    assert "2/3" in result.assessment
    assert "reference key points covered" in result.assessment


# ─────────────────────────────────────────────
# AlignmentMetric
# ─────────────────────────────────────────────


def test_alignment_uses_input_as_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_reference_prompts: list[str] = []

    class _TrackingAlignment(AlignmentMetric):
        async def _extract_reference_points(self, input: str, ground_truth: str | None) -> list[str]:
            captured_reference_prompts.append(self.reference_extraction_prompt(input, ground_truth))
            return ["ref point"]

        async def _extract_claims(self, output: str) -> list[str]:
            return ["claim"]

        async def _generate_verdicts(self, claims, reference_points):
            from prompt_model._metrics.base_claim_metric import ClaimVerdict

            return [ClaimVerdict(claim="claim", passes=True)]

        async def _attribute_nodes(self, failing_verdicts, prompt_with_ids):
            return []

    metric = _TrackingAlignment(_CONFIG)
    asyncio.run(metric.evaluate(_PROMPT_MD, "THE SOURCE TEXT", "output", None))
    assert any("THE SOURCE TEXT" in p for p in captured_reference_prompts)


def test_alignment_does_not_require_ground_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    class _StubAlignment(AlignmentMetric):
        async def _extract_claims(self, output):
            return []

        async def _extract_reference_points(self, input, ground_truth):
            return []

        async def _generate_verdicts(self, claims: list[str], reference_points: list[str]):
            return []

        async def _attribute_nodes(self, failing_verdicts, prompt_with_ids):
            return []

    metric = _StubAlignment(_CONFIG)
    result: MetricResult = asyncio.run(metric.evaluate(_PROMPT_MD, "input", "output", None))
    assert isinstance(result, MetricResult)


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
