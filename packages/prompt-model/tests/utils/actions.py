from __future__ import annotations

from prompt_model._protocols.action import Action
from prompt_model.service.actions import SkipReason
from prompt_model.service.parsing.parse_prompt import parse_from_string

from . import parsing as p
from ._short_hand import doc_from_shorthand


def check_against_md(input_markdown: str, action: Action, expected_markdown: str) -> None:
    actual_tree = parse_from_string(input_markdown)
    action.apply(actual_tree)
    p.check_obj_against_md(actual_tree, expected_markdown)


def check_against_sh(markdown: str, action: Action, shorthand: str) -> None:
    tree = parse_from_string(markdown)
    action.apply(tree)
    p.check_obj_against_sh(tree, shorthand)


def check_can_apply(markdown: str, action: Action, result: SkipReason | None) -> None:
    tree = parse_from_string(markdown)
    can_apply: SkipReason | None = action.validate(tree)
    if result is None:
        assert can_apply is None
    else:
        assert result == can_apply


def check_undo(markdown: str, actions: list[Action]) -> None:
    tree = parse_from_string(markdown)
    original = tree.model_copy(deep=True)

    undo_stack: list[Action] = []
    for action in actions:
        undo_stack.append(action.apply(tree))

    while undo_stack:
        undo_stack.pop().apply(tree)

    p.check_obj_against_obj(tree, original)


def check_undo_from_sh(shorthand: str, actions: list[Action]) -> None:
    tree = doc_from_shorthand(shorthand)
    original = tree.model_copy(deep=True)

    undo_stack: list[Action] = []
    for action in actions:
        undo_stack.append(action.apply(tree))

    while undo_stack:
        undo_stack.pop().apply(tree)

    p.check_obj_against_obj(tree, original)
