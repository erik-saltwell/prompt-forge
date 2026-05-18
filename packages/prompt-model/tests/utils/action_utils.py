from __future__ import annotations

from prompt_model._protocols.action import Action
from prompt_model.service.actions import SkipReason
from prompt_model.service.parsing.parse_prompt import parse_from_string

from .parsing_utils import assert_tree_matches_shorthand, assert_trees_structurally_equal


def assert_action_against_shorthand(markdown: str, action: Action, shorthand: str) -> None:
    tree = parse_from_string(markdown)
    action.apply(tree)
    assert_tree_matches_shorthand(tree, shorthand)


def assert_can_apply(markdown: str, action: Action, result: SkipReason | None) -> None:
    tree = parse_from_string(markdown)
    can_apply: SkipReason | None = action.validate(tree)
    if result is None:
        assert can_apply is None
    else:
        assert result == can_apply


def assert_undo(markdown: str, actions: list[Action]) -> None:
    tree = parse_from_string(markdown)
    original = tree.model_copy(deep=True)

    undo_stack: list[Action] = []
    for action in actions:
        undo_stack.append(action.apply(tree))

    while undo_stack:
        undo_stack.pop().apply(tree)

    assert_trees_structurally_equal(tree, original)
