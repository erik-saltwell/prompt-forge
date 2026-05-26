from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from prompt_model._actions.inputs import ActionBatch
from prompt_model._actor.revise import PromptAndActions, _process_feedback
from prompt_model._metrics._aggregator import AggregatedNodeBucket
from prompt_model._metrics.result import IssueSignal
from prompt_model._prompt import Document
from prompt_model._prompt.parsing.parse_prompt import parse_from_string
from prompt_model.config import LiteLLMConfig
from prompt_model.strategies.prompt_rendering_strategy import XmlRenderPromptStrategy
from prompt_model.strategies.redaction_strategy import ContextualRedactionStrategy
from prompt_model.strategies.signal_render_strategy import MarkdownSignalRenderingStrategy


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


def _config() -> LiteLLMConfig:
    return LiteLLMConfig(model="anthropic/claude-sonnet-4-6")


def _strategies() -> tuple[ContextualRedactionStrategy, XmlRenderPromptStrategy, MarkdownSignalRenderingStrategy]:
    return ContextualRedactionStrategy(), XmlRenderPromptStrategy(), MarkdownSignalRenderingStrategy()


def _run_per_node_pass(
    tree: Document,
    bucket: AggregatedNodeBucket,
    preserve: list[str],
    mock: AsyncMock,
) -> PromptAndActions | None:
    redactor, renderer, signaler = _strategies()
    with patch("prompt_model._actor.revise.acomplete", mock):
        return asyncio.run(
            _process_feedback(
                tree=tree,
                bucket=bucket,
                preserve=preserve,
                llm_config=_config(),
                prompt_redactor=redactor,
                prompt_renderer=renderer,
                signal_renderer=signaler,
            )
        )


def test_happy_path_returns_prompt_and_actions() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    batch = ActionBatch.model_validate(
        {
            "reasoning": "tighten",
            "actions": [{"action": "rewrite_node", "id": "1.1", "text": "new body"}],
        }
    )
    mock = AsyncMock(return_value=batch.model_dump_json())

    result = _run_per_node_pass(tree, _bucket("1.1"), [], mock)

    assert result is not None
    assert result.actions.reasoning == batch.reasoning
    assert "new body" in result.prompt.to_markdown()


def test_unparseable_json_from_acomplete_returns_none() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    mock = AsyncMock(return_value="{invalid json}")

    result = _run_per_node_pass(tree, _bucket("1.1"), [], mock)

    assert result is None


def test_invalid_schema_from_acomplete_returns_none() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    # Missing required 'reasoning' field — model_validate_json will raise ValidationError
    mock = AsyncMock(return_value='{"actions": []}')

    result = _run_per_node_pass(tree, _bucket("1.1"), [], mock)

    assert result is None


def test_empty_actions_returns_none() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    batch = ActionBatch(reasoning="no changes needed", actions=[])
    mock = AsyncMock(return_value=batch.model_dump_json())

    result = _run_per_node_pass(tree, _bucket("1.1"), [], mock)

    assert result is None


def test_all_actions_skipped_returns_none() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    batch = ActionBatch.model_validate(
        {
            "reasoning": "tighten",
            "actions": [{"action": "rewrite_node", "id": "99.99", "text": "x"}],
        }
    )
    mock = AsyncMock(return_value=batch.model_dump_json())

    result = _run_per_node_pass(tree, _bucket("1.1"), [], mock)

    assert result is None


def test_transport_error_propagates() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    mock = AsyncMock(side_effect=RuntimeError("503"))

    with pytest.raises(RuntimeError, match="503"):
        _run_per_node_pass(tree, _bucket("1.1"), [], mock)


def test_user_prompt_contains_tree_signals_and_preserve() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    batch = ActionBatch.model_validate(
        {
            "reasoning": "tighten",
            "actions": [{"action": "rewrite_node", "id": "1.1", "text": "new"}],
        }
    )
    mock = AsyncMock(return_value=batch.model_dump_json())

    _run_per_node_pass(tree, _bucket("1.1"), ["never drop the alpha heading"], mock)

    user_prompt: str = mock.call_args.args[1]
    assert "<prompt>" in user_prompt
    assert "<feedback>" in user_prompt
    assert "<preserve>" in user_prompt
    assert "never drop the alpha heading" in user_prompt
    assert "vague" in user_prompt  # rendered signal rationale
