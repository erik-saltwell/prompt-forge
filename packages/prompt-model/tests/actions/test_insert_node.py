from __future__ import annotations

from prompt_model.service.actions import Action, AddNodeAction, LocationAnchor, SkipReason, parse_action

from ..utils import actions as act


def test_simple_add_node() -> None:
    input_md = """# foo

test test test

- one
  ::: guidance
  - g one
  - g two
  :::
- two
"""

    expected_md: str = """# foo

test test test

- one
  ::: guidance
  - g one
  - g two
  :::
- two

a small dog
"""

    action: Action = AddNodeAction("a small dog", LocationAnchor(kind="last_child", target="1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_paragraph_string_shorthand() -> None:
    input_md = """# foo

para one
"""
    expected_md = """# foo

para one

new para
"""
    action = AddNodeAction("new para", LocationAnchor(kind="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_paragraph_before() -> None:
    input_md = """# foo

para one
"""
    expected_md = """# foo

new para

para one
"""
    action = AddNodeAction("new para", LocationAnchor(kind="before", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_first_child_of_section() -> None:
    input_md = """# foo

existing
"""
    expected_md = """# foo

inserted

existing
"""
    action = AddNodeAction("inserted", LocationAnchor(kind="first_child", target="1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_last_child_of_section() -> None:
    input_md = """# foo

existing
"""
    expected_md = """# foo

existing

inserted
"""
    action = AddNodeAction("inserted", LocationAnchor(kind="last_child", target="1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_section_with_body() -> None:
    input_md = """# foo

intro
"""
    expected_md = """# foo

intro

## bar

in bar
"""
    payload = {
        "node_type": "Section",
        "level": 2,
        "text": "bar",
        "children": [{"node_type": "Paragraph", "text": "in bar"}],
    }
    action = AddNodeAction(payload, LocationAnchor(kind="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_invalid_anchor_target() -> None:
    action = AddNodeAction("x", LocationAnchor(kind="after", target="9.9.9"))
    act.check_can_apply("body\n", action, SkipReason.InvalidAnchor)


def test_insert_invalid_subtree_string_empty() -> None:
    action = AddNodeAction("", LocationAnchor(kind="after", target="1"))
    act.check_can_apply("body\n", action, SkipReason.InvalidSubtree)


def test_insert_invalid_subtree_bad_dict() -> None:
    action = AddNodeAction(
        {"node_type": "NotAType", "text": "x"},
        LocationAnchor(kind="after", target="1"),
    )
    act.check_can_apply("body\n", action, SkipReason.InvalidSubtree)


def test_insert_empty_container_rejected() -> None:
    payload = {"node_type": "Section", "level": 2, "text": "empty", "children": []}
    action = AddNodeAction(payload, LocationAnchor(kind="last_child", target="1"))
    act.check_can_apply("# top\n\nbody\n", action, SkipReason.InvalidSubtree)


def test_insert_heading_level_skip_rejected() -> None:
    payload = {
        "node_type": "Section",
        "level": 4,
        "text": "too deep",
        "children": [{"node_type": "Paragraph", "text": "x"}],
    }
    action = AddNodeAction(payload, LocationAnchor(kind="last_child", target="1"))
    act.check_can_apply("# top\n\nbody\n", action, SkipReason.InvalidStructure)


# ---------- Lists & ListItems ----------


def test_insert_list_item_into_existing_list() -> None:
    input_md = """- a
- b
"""
    expected_md = """- a
- new
- b
"""
    payload = {"node_type": "ListItem", "text": "new"}
    action = AddNodeAction(payload, LocationAnchor(kind="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_list_item_at_first_child_of_list() -> None:
    input_md = """- a
- b
"""
    expected_md = """- new
- a
- b
"""
    payload = {"node_type": "ListItem", "text": "new"}
    action = AddNodeAction(payload, LocationAnchor(kind="first_child", target="1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_paragraph_into_list_rejected() -> None:
    # List children must be ListItem only — inserting a Paragraph as a child
    # of List should fail structural validation.
    payload = {"node_type": "Paragraph", "text": "stray"}
    action = AddNodeAction(payload, LocationAnchor(kind="last_child", target="1"))
    act.check_can_apply("- a\n- b\n", action, SkipReason.InvalidStructure)


def test_insert_codeblock_into_listitem() -> None:
    input_md = """- item
"""
    expected_md = """- item

  ```python
  print(1)
  ```
"""
    payload = {"node_type": "CodeBlock", "text": "print(1)", "info": "python"}
    action = AddNodeAction(payload, LocationAnchor(kind="last_child", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


# ---------- Inline annotations in inserted subtrees ----------


def test_insert_paragraph_with_examples() -> None:
    input_md = """# top

intro
"""
    expected_md = """# top

intro

new para

::: examples
an example
:::
"""
    payload = {
        "node_type": "Paragraph",
        "text": "new para",
        "examples": {
            "node_type": "ExamplesGroup",
            "children": [{"node_type": "Annotation", "text": "an example"}],
        },
    }
    action = AddNodeAction(payload, LocationAnchor(kind="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_list_item_with_guidance() -> None:
    input_md = """- a
"""
    expected_md = """- a
- new
  ::: guidance
  - g one
  - g two
  :::
"""
    payload = {
        "node_type": "ListItem",
        "text": "new",
        "guidance": {
            "node_type": "GuidanceGroup",
            "children": [
                {"node_type": "Annotation", "text": "g one"},
                {"node_type": "Annotation", "text": "g two"},
            ],
        },
    }
    action = AddNodeAction(payload, LocationAnchor(kind="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


# ---------- Other leaf types & structural flags ----------


def test_insert_codeblock_with_info_round_trips() -> None:
    input_md = """# top

intro
"""
    expected_md = """# top

intro

```rust
fn main() {}
```
"""
    payload = {"node_type": "CodeBlock", "text": "fn main() {}", "info": "rust"}
    action = AddNodeAction(payload, LocationAnchor(kind="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_blockquote() -> None:
    input_md = """# top

intro
"""
    expected_md = """# top

intro

> quoted text
"""
    payload = {"node_type": "Blockquote", "text": "quoted text"}
    action = AddNodeAction(payload, LocationAnchor(kind="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_ordered_list_preserves_ordered_flag() -> None:
    input_md = """# top

intro
"""
    expected_md = """# top

intro

1. first
2. second
"""
    payload = {
        "node_type": "List",
        "ordered": True,
        "children": [
            {"node_type": "ListItem", "text": "first"},
            {"node_type": "ListItem", "text": "second"},
        ],
    }
    action = AddNodeAction(payload, LocationAnchor(kind="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


# ---------- Document-root anchor (target="") ----------


def test_insert_first_child_of_document() -> None:
    input_md = """# top

intro
"""
    expected_md = """preface

# top

intro
"""
    action = AddNodeAction("preface", LocationAnchor(kind="first_child", target=""))
    act.check_against_md(input_md, action, expected_md)


def test_insert_last_child_of_document() -> None:
    input_md = """# top

intro
"""
    expected_md = """# top

intro

postscript
"""
    action = AddNodeAction("postscript", LocationAnchor(kind="last_child", target=""))
    act.check_against_md(input_md, action, expected_md)


def test_parse_action_rejects_empty_anchor_target() -> None:
    # The JSON entrypoint requires a non-empty target string in the anchor.
    # The Document-root "" convention is only available to code that builds
    # LocationAnchor directly.
    assert parse_action({"type": "insert_node", "subtree": "x", "anchor": {"first_child": ""}}) == SkipReason.MissingRequired


# ---------- Edge anchor positions inside a Section ----------


def test_insert_before_first_child_of_section() -> None:
    input_md = """# top

para one

para two
"""
    expected_md = """# top

inserted

para one

para two
"""
    action = AddNodeAction("inserted", LocationAnchor(kind="before", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_after_last_child_of_section() -> None:
    input_md = """# top

para one

para two
"""
    expected_md = """# top

para one

para two

inserted
"""
    action = AddNodeAction("inserted", LocationAnchor(kind="after", target="1.2"))
    act.check_against_md(input_md, action, expected_md)


# ---------- parse_action ----------


def test_parse_action_builds_insert_node_with_string_subtree() -> None:
    result = parse_action({"type": "insert_node", "subtree": "hello", "anchor": {"after": "1.1"}})
    assert isinstance(result, AddNodeAction)
    assert result.subtree_raw == "hello"


def test_parse_action_builds_insert_node_with_dict_subtree() -> None:
    result = parse_action(
        {
            "type": "insert_node",
            "subtree": {"node_type": "Paragraph", "text": "x"},
            "anchor": {"first_child": "1"},
        }
    )
    assert isinstance(result, AddNodeAction)


def test_parse_action_missing_subtree() -> None:
    assert parse_action({"type": "insert_node", "anchor": {"after": "1.1"}}) == SkipReason.MissingRequired


def test_parse_action_missing_anchor() -> None:
    assert parse_action({"type": "insert_node", "subtree": "x"}) == SkipReason.MissingRequired


def test_parse_action_bad_anchor() -> None:
    assert parse_action({"type": "insert_node", "subtree": "x", "anchor": {"bogus": "1"}}) == SkipReason.MissingRequired
