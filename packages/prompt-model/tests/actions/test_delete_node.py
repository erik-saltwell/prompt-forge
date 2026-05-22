from __future__ import annotations

from prompt_model._actions import (
    RemoveNodeAction,
    SkipReason,
    parse_action,
)

from ..utils import actions as act


def test_remove_paragraph_between_siblings() -> None:
    input_md = """# foo

para one

para two

para three
"""
    expected_md = """# foo

para one

para three
"""
    act.check_against_md(input_md, RemoveNodeAction("1.2"), expected_md)


def test_remove_first_child() -> None:
    input_md = """# foo

para one

para two
"""
    expected_md = """# foo

para two
"""
    act.check_against_md(input_md, RemoveNodeAction("1.1"), expected_md)


def test_remove_section_with_subtree() -> None:
    input_md = """# foo

body

## bar

inner

## baz

other
"""
    expected_md = """# foo

body

## baz

other
"""
    act.check_against_md(input_md, RemoveNodeAction("1.2"), expected_md)


def test_remove_leaving_empty_document_rejected() -> None:
    # Removing the sole top-level child would produce empty markdown,
    # which validate-prompt rejects → skip.
    act.check_can_apply("body\n", RemoveNodeAction("1"), SkipReason.InvalidStructure)


def test_remove_nonexistent_id_rejected() -> None:
    act.check_can_apply("# h\n\nbody\n", RemoveNodeAction("9.9.9"), SkipReason.TargetNotFound)


def test_remove_annotation_id_rejected() -> None:
    # delete_node is node-only in v1 — annotation removal goes through remove_example.
    md = "body\n\n::: examples\nex\n:::\n"
    act.check_can_apply(md, RemoveNodeAction("1.e1"), SkipReason.TargetNotFound)


# ---------- Lists & ListItems ----------


def test_remove_list_item_from_multi_item_list() -> None:
    input_md = """- a
- b
- c
"""
    expected_md = """- a
- c
"""
    act.check_against_md(input_md, RemoveNodeAction("1.2"), expected_md)


def test_remove_only_list_item_rejected() -> None:
    # Removing the only ListItem leaves an empty List, which is invalid.
    act.check_can_apply("- solo\n", RemoveNodeAction("1.1"), SkipReason.InvalidStructure)


# ---------- Hosts with annotations attached ----------


def test_remove_paragraph_with_annotations() -> None:
    input_md = """# top

doomed

::: examples
ex one
:::

::: guidance
g one
:::

survivor
"""
    expected_md = """# top

survivor
"""
    act.check_against_md(input_md, RemoveNodeAction("1.1"), expected_md)


# ---------- Other leaf types ----------


def test_remove_blockquote() -> None:
    input_md = """# top

intro

> quoted
"""
    expected_md = """# top

intro
"""
    act.check_against_md(input_md, RemoveNodeAction("1.2"), expected_md)


# ---------- parse_action ----------


def test_parse_action_builds_delete_node() -> None:
    result = parse_action({"type": "delete_node", "id": "1.1"})
    assert isinstance(result, RemoveNodeAction)
    assert result.node_id == "1.1"


def test_parse_action_ignores_extra_fields() -> None:
    result = parse_action({"type": "delete_node", "id": "1.1", "x": 9})
    assert isinstance(result, RemoveNodeAction)


def test_parse_action_missing_id() -> None:
    assert parse_action({"type": "delete_node"}) == SkipReason.MissingRequired


def test_parse_action_empty_id() -> None:
    assert parse_action({"type": "delete_node", "id": ""}) == SkipReason.MissingRequired


def test_parse_action_non_string_id() -> None:
    assert parse_action({"type": "delete_node", "id": 42}) == SkipReason.MissingRequired
