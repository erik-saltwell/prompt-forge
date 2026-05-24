from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from prompt_model._actions.inputs import ActionBatch
from prompt_model._actor.revise import revise
from prompt_model._candidate.candidate import Candidate
from prompt_model._metrics.result import IssueSignal, MetricResult
from prompt_model._prompt import Document
from prompt_model._prompt.parsing.parse_prompt import parse_from_string
from prompt_model.config import LiteLLMConfig


def _signal(culprit_id: str) -> IssueSignal:
    return IssueSignal(
        culprit_node_id=culprit_id,
        rationale="vague",
        target_behavior="be specific",
        success_criterion="contains an example",
        input_snippet="in",
        output_snippet="out",
    )


def _metric_result(*culprit_ids: str) -> MetricResult:
    return MetricResult(
        metric_name="m1",
        score=0.5,
        assessment="needs work",
        signals=[_signal(cid) for cid in culprit_ids],
        preserve=[],
    )


def _tree() -> Document:
    return parse_from_string("# alpha\n\nbody one\n\n# beta\n\nbody two\n")


def _candidate(results: list[MetricResult]) -> Candidate:
    return Candidate(prompt=_tree(), case_ids=[1, 2, 3], results=results)


def _config() -> LiteLLMConfig:
    return LiteLLMConfig(model="anthropic/claude-sonnet-4-6")


def _valid_batch() -> ActionBatch:
    return ActionBatch.model_validate(
        {
            "reasoning": "tighten",
            "actions": [{"action": "rewrite_node", "id": "1.1", "text": "tightened"}],
        }
    )


def _empty_batch() -> ActionBatch:
    return ActionBatch(reasoning="no changes", actions=[])


def _run_revise(
    candidate: Candidate,
    feedback_mock: AsyncMock,
    structural_mock: AsyncMock,
) -> list[Document]:
    with (
        patch("prompt_model._actor.revise.acomplete", feedback_mock),
        patch("prompt_model._actor._structural_actor.acomplete", structural_mock),
    ):
        return asyncio.run(revise(candidate, feedback_llm_config=_config()))


def test_returns_empty_when_candidate_has_no_results() -> None:
    candidate = _candidate(results=[])
    feedback_mock = AsyncMock()
    structural_mock = AsyncMock()

    result = _run_revise(candidate, feedback_mock, structural_mock)

    assert result == []
    feedback_mock.assert_not_called()
    structural_mock.assert_not_called()


def test_returns_empty_when_aggregation_produces_no_buckets() -> None:
    # Result exists but has no signals → aggregator emits zero buckets.
    candidate = _candidate(results=[_metric_result()])  # no culprit ids → no signals
    feedback_mock = AsyncMock()
    structural_mock = AsyncMock()

    result = _run_revise(candidate, feedback_mock, structural_mock)

    assert result == []
    feedback_mock.assert_not_called()


def test_fans_out_one_pipeline_per_bucket() -> None:
    # Two distinct culprit ids → two buckets.
    candidate = _candidate(results=[_metric_result("1.1", "2.1")])
    feedback_mock = AsyncMock(return_value=_valid_batch())
    structural_mock = AsyncMock(return_value=_empty_batch())  # structural is a no-op pass-through

    result = _run_revise(candidate, feedback_mock, structural_mock)

    assert len(result) == 2
    assert feedback_mock.call_count == 2
    assert structural_mock.call_count == 2
    for doc in result:
        assert "tightened" in doc.to_markdown()


def test_drops_buckets_whose_per_node_pass_yields_nothing() -> None:
    candidate = _candidate(results=[_metric_result("1.1", "2.1")])
    # Per-node returns empty actions for every call → every bucket drops.
    feedback_mock = AsyncMock(return_value=_empty_batch())
    structural_mock = AsyncMock(return_value=_empty_batch())

    result = _run_revise(candidate, feedback_mock, structural_mock)

    assert result == []
    structural_mock.assert_not_called()


def test_transport_error_propagates() -> None:
    candidate = _candidate(results=[_metric_result("1.1")])
    feedback_mock = AsyncMock(side_effect=RuntimeError("503"))
    structural_mock = AsyncMock(return_value=_empty_batch())

    with pytest.raises(RuntimeError, match="503"):
        _run_revise(candidate, feedback_mock, structural_mock)
