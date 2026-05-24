from __future__ import annotations

import pytest
from prompt_model._actor._resources import load_prompt


def test_loads_feedback_actor_prompt() -> None:
    content: str = load_prompt("feedback_actor")
    assert isinstance(content, str)


def test_loads_structural_actor_prompt() -> None:
    content: str = load_prompt("structural_actor")
    assert isinstance(content, str)


def test_raises_for_missing_prompt() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist")
