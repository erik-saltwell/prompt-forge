from __future__ import annotations

import pytest
from prompt_model._actor._resources import load_prompt

_ACTION_DISCRIMINATORS: list[str] = [
    "rewrite_node",
    "delete_node",
    "insert_node",
    "move_node",
    "add_example",
    "update_example",
    "remove_example",
    "add_guidance",
    "update_guidance",
    "remove_guidance",
]

_INPUT_BLOCK_TAGS: list[str] = ["<prompt>", "<feedback>", "<preserve>"]


def test_loads_feedback_actor_prompt() -> None:
    content: str = load_prompt("feedback_actor")
    assert isinstance(content, str)


def test_loads_structural_actor_prompt() -> None:
    content: str = load_prompt("structural_actor")
    assert isinstance(content, str)


def test_raises_for_missing_prompt() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist")


def test_feedback_actor_prompt_is_non_empty() -> None:
    body: str = load_prompt("feedback_actor")
    assert len(body) >= 200, f"feedback_actor prompt is suspiciously short ({len(body)} chars)"


def test_feedback_actor_prompt_documents_every_action() -> None:
    body: str = load_prompt("feedback_actor")
    missing: list[str] = [name for name in _ACTION_DISCRIMINATORS if name not in body]
    assert not missing, f"feedback_actor prompt is missing action documentation for: {missing}"


def test_feedback_actor_prompt_describes_input_block_tags() -> None:
    body: str = load_prompt("feedback_actor")
    missing: list[str] = [tag for tag in _INPUT_BLOCK_TAGS if tag not in body]
    assert not missing, f"feedback_actor prompt does not mention input wrapper tags: {missing}"
