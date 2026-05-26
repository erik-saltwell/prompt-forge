from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from prompt_model._actions.inputs import ActionBatch
from prompt_model._actor.revise import _process_bucket
from prompt_model._metrics._aggregator import AggregatedNodeBucket
from prompt_model._metrics.result import IssueSignal
from prompt_model._prompt import Document
from prompt_model._prompt.parsing.parse_prompt import parse_from_string
from prompt_model.config import LiteLLMConfig
from prompt_model.strategies.prompt_rendering_strategy import XmlRenderPromptStrategy
from prompt_model.strategies.redaction_strategy import ContextualRedactionStrategy
from prompt_model.strategies.signal_render_strategy import MarkdownSignalRenderingStrategy
from prompt_model.strategies.structural_cleanup_strategy import AlwaysCleanup, NeverCleanup, StructuralCleanupDecisionProtocol


def _bucket(culprit_id: str = "1.1") -> AggregatedNodeBucket:
    return AggregatedNodeBucket(
        culprit_node_id=culprit_id,
        signals=[
            IssueSignal(
                culprit_node_id=culprit_id,
                rationale="vague",
                target_behavior="be specific",
                success_criterion="contains an example",
                input_snippet="in",
                output_snippet="out",
            )
        ],
    )


def _config(model: str = "anthropic/claude-sonnet-4-6") -> LiteLLMConfig:
    return LiteLLMConfig(model=model)


def _per_node_batch() -> ActionBatch:
    return ActionBatch.model_validate(
        {
            "reasoning": "tighten",
            "actions": [{"action": "rewrite_node", "id": "1.1", "text": "per-node"}],
        }
    )


def _structural_batch() -> ActionBatch:
    return ActionBatch.model_validate(
        {
            "reasoning": "cleanup",
            "actions": [{"action": "rewrite_node", "id": "1.1", "text": "structural"}],
        }
    )


def _run_pipeline(
    tree: Document,
    *,
    feedback_mock: AsyncMock,
    structural_mock: AsyncMock,
    structural_cleanup_decider: StructuralCleanupDecisionProtocol,
    feedback_llm_config: LiteLLMConfig | None = None,
    structural_llm_config: LiteLLMConfig | None = None,
) -> Document | None:
    feedback_cfg = feedback_llm_config if feedback_llm_config is not None else _config()
    with (
        patch("prompt_model._actor.revise.acomplete", feedback_mock),
        patch("prompt_model._actor._structural_actor.acomplete", structural_mock),
    ):
        return asyncio.run(
            _process_bucket(
                tree=tree,
                bucket=_bucket("1.1"),
                preserve=[],
                feedback_llm_config=feedback_cfg,
                structural_llm_config=structural_llm_config,
                prompt_redactor=ContextualRedactionStrategy(),
                prompt_renderer=XmlRenderPromptStrategy(),
                signal_renderer=MarkdownSignalRenderingStrategy(),
                structural_cleanup_decider=structural_cleanup_decider,
            )
        )


def test_per_node_drop_returns_none_and_skips_structural() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    feedback_mock = AsyncMock(return_value=ActionBatch(reasoning="none", actions=[]).model_dump_json())
    structural_mock = AsyncMock(return_value=_structural_batch().model_dump_json())

    result = _run_pipeline(tree, feedback_mock=feedback_mock, structural_mock=structural_mock, structural_cleanup_decider=AlwaysCleanup())

    assert result is None
    structural_mock.assert_not_called()


def test_predicate_false_returns_per_node_prompt_and_skips_structural() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    feedback_mock = AsyncMock(return_value=_per_node_batch().model_dump_json())
    structural_mock = AsyncMock(return_value=_structural_batch().model_dump_json())

    result = _run_pipeline(tree, feedback_mock=feedback_mock, structural_mock=structural_mock, structural_cleanup_decider=NeverCleanup())

    assert result is not None
    assert "per-node" in result.to_markdown()
    structural_mock.assert_not_called()


def test_predicate_true_runs_structural_and_returns_its_document() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    feedback_mock = AsyncMock(return_value=_per_node_batch().model_dump_json())
    structural_mock = AsyncMock(return_value=_structural_batch().model_dump_json())

    result = _run_pipeline(tree, feedback_mock=feedback_mock, structural_mock=structural_mock, structural_cleanup_decider=AlwaysCleanup())

    assert result is not None
    assert "structural" in result.to_markdown()
    structural_mock.assert_called_once()


def test_structural_uses_override_config_when_provided() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    feedback_cfg = _config("anthropic/claude-sonnet-4-6")
    structural_cfg = _config("anthropic/claude-haiku-4-5-20251001")
    feedback_mock = AsyncMock(return_value=_per_node_batch().model_dump_json())
    structural_mock = AsyncMock(return_value=_structural_batch().model_dump_json())

    _run_pipeline(
        tree,
        feedback_mock=feedback_mock,
        structural_mock=structural_mock,
        structural_cleanup_decider=AlwaysCleanup(),
        feedback_llm_config=feedback_cfg,
        structural_llm_config=structural_cfg,
    )

    assert structural_mock.call_args.args[2] is structural_cfg
    assert feedback_mock.call_args.args[2] is feedback_cfg


def test_structural_falls_back_to_feedback_config_when_override_absent() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    feedback_cfg = _config()
    feedback_mock = AsyncMock(return_value=_per_node_batch().model_dump_json())
    structural_mock = AsyncMock(return_value=_structural_batch().model_dump_json())

    _run_pipeline(
        tree,
        feedback_mock=feedback_mock,
        structural_mock=structural_mock,
        structural_cleanup_decider=AlwaysCleanup(),
        feedback_llm_config=feedback_cfg,
        structural_llm_config=None,
    )

    assert structural_mock.call_args.args[2] is feedback_cfg


def test_per_node_transport_error_propagates() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    feedback_mock = AsyncMock(side_effect=RuntimeError("503 from feedback"))
    structural_mock = AsyncMock(return_value=_structural_batch())

    with pytest.raises(RuntimeError, match="503 from feedback"):
        _run_pipeline(
            tree,
            feedback_mock=feedback_mock,
            structural_mock=structural_mock,
            structural_cleanup_decider=AlwaysCleanup(),
        )
    structural_mock.assert_not_called()


def test_structural_transport_error_propagates() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    feedback_mock = AsyncMock(return_value=_per_node_batch().model_dump_json())
    structural_mock = AsyncMock(side_effect=RuntimeError("503 from structural"))

    with pytest.raises(RuntimeError, match="503 from structural"):
        _run_pipeline(
            tree,
            feedback_mock=feedback_mock,
            structural_mock=structural_mock,
            structural_cleanup_decider=AlwaysCleanup(),
        )
