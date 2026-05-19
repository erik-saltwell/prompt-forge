from __future__ import annotations

from prompt_model.service.actions import (
    Action,
    RewriteNodeAction,
    SkipReason,
    parse_action,
)

from ..utils import actions as act


def test_simple_rewrite_node() -> None:
    input_md = """# foo
test test test
- test a
  ::: guidance
  hsdaksjh laksdjsal hlksdj
  :::
- test b
"""
    afer_replace_header = """# bar

test test test

- test a
  ::: guidance
  hsdaksjh laksdjsal hlksdj
  :::
- test b
"""
    afer_replace_text = """# bar

a small dog

- test a
  ::: guidance
  hsdaksjh laksdjsal hlksdj
  :::
- test b
"""
    afer_replace_list_one = """# bar

a small dog

- something
  ::: guidance
  hsdaksjh laksdjsal hlksdj
  :::
- test b
"""
    afer_replace_list_two = """# bar

a small dog

- something
  ::: guidance
  hsdaksjh laksdjsal hlksdj
  :::
- something else
"""
    actions: list[Action] = [
        RewriteNodeAction("1", "bar"),
        RewriteNodeAction("1.1", "a small dog"),
        RewriteNodeAction("1.2.1", "something"),
        RewriteNodeAction("1.2.2", "something else"),
    ]
    act.check_against_md(input_md, actions[0], afer_replace_header)
    act.check_against_md(afer_replace_header, actions[1], afer_replace_text)
    act.check_against_md(afer_replace_text, actions[2], afer_replace_list_one)
    act.check_against_md(afer_replace_list_one, actions[3], afer_replace_list_two)

    act.check_undo(input_md, actions)


def test_replace_with_annotations_in_list() -> None:
    input_md = """# bar

a small dog

- something
  ::: guidance
  hsdaksjh laksdjsal hlksdj
  :::
  ::: example
  asd asdfdsg asdasd
  :::
- test b
"""
    expected_md = """# bar

a small dog

- something
  ::: examples
  asd asdfdsg asdasd
  :::
  ::: guidance
  hsdaksjh laksdjsal hlksdj
  :::
- something else
"""
    action: Action = RewriteNodeAction("1.2.2", "something else")
    act.check_against_md(input_md, action, expected_md)


# ---------- Per-node-type validation & happy paths ----------


def test_section_strips_leading_hash_markers() -> None:
    input_md = "# old\n"
    expected_md = "# new\n"
    act.check_against_md(input_md, RewriteNodeAction("1", "## new"), expected_md)


def test_section_rejects_newline_in_text() -> None:
    act.check_can_apply("# old\n", RewriteNodeAction("1", "first\nsecond"), SkipReason.InvalidContent)


def test_paragraph_rejects_triple_colon() -> None:
    act.check_can_apply("body\n", RewriteNodeAction("1", "before ::: after"), SkipReason.InvalidContent)


def test_listitem_rejects_triple_colon() -> None:
    act.check_can_apply("- li\n", RewriteNodeAction("1.1", "x ::: y"), SkipReason.InvalidContent)


def test_codeblock_happy_path_preserves_info() -> None:
    input_md = "```python\nprint(1)\n```\n"
    expected_md = "```python\nprint(2)\n```\n"
    act.check_against_md(input_md, RewriteNodeAction("1", "print(2)"), expected_md)


def test_codeblock_rejects_triple_backtick() -> None:
    md = "```python\nprint(1)\n```\n"
    act.check_can_apply(md, RewriteNodeAction("1", "x\n```\ny"), SkipReason.InvalidContent)


def test_codeblock_rejects_triple_colon() -> None:
    md = "```python\nprint(1)\n```\n"
    act.check_can_apply(md, RewriteNodeAction("1", "x ::: y"), SkipReason.InvalidContent)


def test_blockquote_rejects_triple_colon() -> None:
    act.check_can_apply("> quoted\n", RewriteNodeAction("1", "no ::: please"), SkipReason.InvalidContent)


def test_table_rejects_text_without_pipe() -> None:
    md = "| a | b |\n| - | - |\n| 1 | 2 |\n"
    act.check_can_apply(md, RewriteNodeAction("1", "just words"), SkipReason.InvalidContent)


def test_table_happy_path_with_pipe() -> None:
    input_md = "| a | b |\n| - | - |\n| 1 | 2 |\n"
    new_table = "| x | y |\n| - | - |\n| 3 | 4 |"
    expected_md = new_table + "\n"
    act.check_against_md(input_md, RewriteNodeAction("1", new_table), expected_md)


# ---------- Empty / whitespace text ----------


def test_empty_text_rejected() -> None:
    act.check_can_apply("body\n", RewriteNodeAction("1", ""), SkipReason.InvalidContent)


def test_whitespace_only_text_rejected() -> None:
    act.check_can_apply("body\n", RewriteNodeAction("1", "   \n\t  "), SkipReason.InvalidContent)


def test_section_text_thats_only_hash_markers_rejected_after_strip() -> None:
    # "## " strips to "" → empty after normalisation → InvalidContent.
    act.check_can_apply("# h\n", RewriteNodeAction("1", "## "), SkipReason.InvalidContent)


# ---------- TargetNotFound paths ----------


def test_nonexistent_id_rejected() -> None:
    act.check_can_apply("# h\n\nbody\n", RewriteNodeAction("9.9.9", "x"), SkipReason.TargetNotFound)


def test_annotation_id_rejected_not_polymorphic() -> None:
    # delete_node accepts annotation IDs; rewrite_node deliberately does not.
    md = "body\n\n::: examples\nex\n:::\n"
    act.check_can_apply(md, RewriteNodeAction("1.e1", "x"), SkipReason.TargetNotFound)


def test_list_id_rejected() -> None:
    # The List node itself has no text — only its ListItem children do.
    act.check_can_apply("- a\n- b\n", RewriteNodeAction("1", "x"), SkipReason.TargetNotFound)


def test_document_id_rejected() -> None:
    # Document has no id and no text.
    act.check_can_apply("body\n", RewriteNodeAction("", "x"), SkipReason.TargetNotFound)


# ---------- Builder / parse_action (JSON entrypoint) ----------


def test_parse_action_builds_rewrite_node_from_well_formed_dict() -> None:
    result = parse_action({"type": "rewrite_node", "id": "1.1", "text": "hello"})
    assert isinstance(result, RewriteNodeAction)
    assert result.node_id == "1.1"
    assert result.text == "hello"


def test_parse_action_ignores_extra_fields() -> None:
    result = parse_action({"type": "rewrite_node", "id": "1.1", "text": "hi", "spurious": True})
    assert isinstance(result, RewriteNodeAction)
    assert result.node_id == "1.1"
    assert result.text == "hi"


def test_parse_action_returns_missing_required_when_id_absent() -> None:
    assert parse_action({"type": "rewrite_node", "text": "x"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_id_empty() -> None:
    assert parse_action({"type": "rewrite_node", "id": "", "text": "x"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_id_not_string() -> None:
    assert parse_action({"type": "rewrite_node", "id": 42, "text": "x"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_text_absent() -> None:
    assert parse_action({"type": "rewrite_node", "id": "1.1"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_text_empty() -> None:
    assert parse_action({"type": "rewrite_node", "id": "1.1", "text": ""}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_text_whitespace_only() -> None:
    assert parse_action({"type": "rewrite_node", "id": "1.1", "text": "  \n\t"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_text_not_string() -> None:
    assert parse_action({"type": "rewrite_node", "id": "1.1", "text": 7}) == SkipReason.MissingRequired
