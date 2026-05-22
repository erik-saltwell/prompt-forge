from __future__ import annotations

from prompt_model._actions import ApplyContext, SkipReason
from prompt_model._actions.protocol import Action
from prompt_model._prompt.parsing.parse_prompt import parse_from_string

from . import parsing as p


def check_against_md(input_markdown: str, action: Action, expected_markdown: str) -> None:
    actual_tree = parse_from_string(input_markdown)
    action.apply(actual_tree, ApplyContext.from_tree(actual_tree))
    p.check_obj_against_md(actual_tree, expected_markdown)


def check_against_sh(markdown: str, action: Action, shorthand: str) -> None:
    tree = parse_from_string(markdown)
    action.apply(tree, ApplyContext.from_tree(tree))
    p.check_obj_against_sh(tree, shorthand)


def check_can_apply(markdown: str, action: Action, result: SkipReason | None) -> None:
    tree = parse_from_string(markdown)
    can_apply: SkipReason | None = action.validate(tree)
    if result is None:
        assert can_apply is None
    else:
        assert result == can_apply
