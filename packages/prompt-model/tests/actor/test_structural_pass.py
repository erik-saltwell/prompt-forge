from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from prompt_model._actions.inputs import ActionBatch
from prompt_model._actor._render_prompt_strategy import XmlRenderPromptStrategy
from prompt_model._actor._structural_actor import _cleanup_structure
from prompt_model._prompt import Document
from prompt_model._prompt.parsing.parse_prompt import parse_from_string
from prompt_model.config import LiteLLMConfig
from pydantic import ValidationError


def _config() -> LiteLLMConfig:
    return LiteLLMConfig(model="anthropic/claude-sonnet-4-6")


def _make_validation_error() -> ValidationError:
    try:
        ActionBatch.model_validate({"actions": []})  # missing required 'reasoning'
    except ValidationError as e:
        return e
    raise AssertionError("expected ValidationError")


def _run_structural_pass(tree: Document, preserve: list[str], mock: AsyncMock) -> Document:
    with patch("prompt_model._actor._structural_actor.acomplete", mock):
        return asyncio.run(
            _cleanup_structure(
                tree=tree,
                preserve=preserve,
                llm_config=_config(),
                prompt_renderer=XmlRenderPromptStrategy(),
            )
        )


def test_happy_path_returns_mutated_document() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    batch = ActionBatch.model_validate(
        {
            "reasoning": "cleanup",
            "actions": [{"action": "rewrite_node", "id": "1.1", "text": "tidied body"}],
        }
    )
    mock = AsyncMock(return_value=batch)

    result = _run_structural_pass(tree, [], mock)

    assert "tidied body" in result.to_markdown()


def test_validation_error_returns_input_tree_unchanged() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    mock = AsyncMock(side_effect=_make_validation_error())

    result = _run_structural_pass(tree, [], mock)

    assert result is tree


def test_empty_actions_returns_input_tree_unchanged() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    batch = ActionBatch(reasoning="nothing to clean up", actions=[])
    mock = AsyncMock(return_value=batch)

    result = _run_structural_pass(tree, [], mock)

    assert result is tree


def test_all_actions_skipped_returns_input_tree_unchanged() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    batch = ActionBatch.model_validate(
        {
            "reasoning": "cleanup",
            "actions": [{"action": "rewrite_node", "id": "99.99", "text": "x"}],
        }
    )
    mock = AsyncMock(return_value=batch)

    result = _run_structural_pass(tree, [], mock)

    assert result is tree


def test_transport_error_propagates() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    mock = AsyncMock(side_effect=RuntimeError("503"))

    with pytest.raises(RuntimeError, match="503"):
        _run_structural_pass(tree, [], mock)


def test_user_prompt_contains_tree_and_preserve_no_feedback() -> None:
    tree = parse_from_string("# alpha\n\nbody\n")
    batch = ActionBatch(reasoning="nothing", actions=[])
    mock = AsyncMock(return_value=batch)

    _run_structural_pass(tree, ["keep the alpha heading"], mock)

    user_prompt: str = mock.call_args.args[1]
    assert "<prompt>" in user_prompt
    assert "<preserve>" in user_prompt
    assert "keep the alpha heading" in user_prompt
    assert "<feedback>" not in user_prompt
