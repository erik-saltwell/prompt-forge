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

    # 'last_child of section 1' = 'after the last sibling' (1.2, the list).
    action: Action = AddNodeAction("a small dog", LocationAnchor(position="after", target="1.2"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_paragraph_string_shorthand() -> None:
    input_md = """# foo

para one
"""
    expected_md = """# foo

para one

new para
"""
    action = AddNodeAction("new para", LocationAnchor(position="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_paragraph_before() -> None:
    input_md = """# foo

para one
"""
    expected_md = """# foo

new para

para one
"""
    action = AddNodeAction("new para", LocationAnchor(position="before", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_before_only_child_of_section() -> None:
    input_md = """# foo

existing
"""
    expected_md = """# foo

inserted

existing
"""
    # 'first_child of section 1' ≡ 'before existing' (1.1).
    action = AddNodeAction("inserted", LocationAnchor(position="before", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_after_only_child_of_section() -> None:
    input_md = """# foo

existing
"""
    expected_md = """# foo

existing

inserted
"""
    # 'last_child of section 1' ≡ 'after existing' (1.1).
    action = AddNodeAction("inserted", LocationAnchor(position="after", target="1.1"))
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
    action = AddNodeAction(payload, LocationAnchor(position="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_invalid_anchor_target() -> None:
    action = AddNodeAction("x", LocationAnchor(position="after", target="9.9.9"))
    act.check_can_apply("body\n", action, SkipReason.InvalidAnchor)


def test_insert_invalid_subtree_string_empty() -> None:
    action = AddNodeAction("", LocationAnchor(position="after", target="1"))
    act.check_can_apply("body\n", action, SkipReason.InvalidSubtree)


def test_insert_invalid_subtree_bad_dict() -> None:
    action = AddNodeAction(
        {"node_type": "NotAType", "text": "x"},
        LocationAnchor(position="after", target="1"),
    )
    act.check_can_apply("body\n", action, SkipReason.InvalidSubtree)


def test_insert_empty_container_rejected() -> None:
    payload = {"node_type": "Section", "level": 2, "text": "empty", "children": []}
    # Target body paragraph (1.1) — 'after 1.1' lands at end of top section.
    action = AddNodeAction(payload, LocationAnchor(position="after", target="1.1"))
    act.check_can_apply("# top\n\nbody\n", action, SkipReason.InvalidSubtree)


def test_insert_heading_level_skip_rejected() -> None:
    payload = {
        "node_type": "Section",
        "level": 4,
        "text": "too deep",
        "children": [{"node_type": "Paragraph", "text": "x"}],
    }
    action = AddNodeAction(payload, LocationAnchor(position="after", target="1.1"))
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
    action = AddNodeAction(payload, LocationAnchor(position="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_list_item_before_first_existing() -> None:
    input_md = """- a
- b
"""
    expected_md = """- new
- a
- b
"""
    payload = {"node_type": "ListItem", "text": "new"}
    # 'first_child of list 1' ≡ 'before 1.1' (the first item).
    action = AddNodeAction(payload, LocationAnchor(position="before", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_paragraph_into_list_rejected() -> None:
    # List children must be ListItem only — inserting a Paragraph as a child
    # of List should fail structural validation.
    payload = {"node_type": "Paragraph", "text": "stray"}
    # After last item (1.1) of the list — lands inside the list as a sibling.
    action = AddNodeAction(payload, LocationAnchor(position="after", target="1.2"))
    act.check_can_apply("- a\n- b\n", action, SkipReason.InvalidStructure)


def test_insert_codeblock_into_leaf_listitem() -> None:
    input_md = """- item
"""
    expected_md = """- item

  ```python
  print(1)
  ```
"""
    payload = {"node_type": "CodeBlock", "text": "print(1)", "info": "python"}
    # Leaf ListItem (1.1) has no children — use 'inside' to place a block child.
    action = AddNodeAction(payload, LocationAnchor(position="inside", target="1.1"))
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
    action = AddNodeAction(payload, LocationAnchor(position="after", target="1.1"))
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
    action = AddNodeAction(payload, LocationAnchor(position="after", target="1.1"))
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
    action = AddNodeAction(payload, LocationAnchor(position="after", target="1.1"))
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
    action = AddNodeAction(payload, LocationAnchor(position="after", target="1.1"))
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
    action = AddNodeAction(payload, LocationAnchor(position="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


# ---------- Document-root anchoring ----------


def test_insert_before_first_root_section() -> None:
    input_md = """# top

intro
"""
    expected_md = """preface

# top

intro
"""
    # Document root has only one section (id "1") — anchor before it.
    action = AddNodeAction("preface", LocationAnchor(position="before", target="1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_after_last_root_section() -> None:
    input_md = """# top

intro
"""
    expected_md = """# top

intro

postscript
"""
    action = AddNodeAction("postscript", LocationAnchor(position="after", target="1"))
    act.check_against_md(input_md, action, expected_md)


def test_parse_action_rejects_empty_target() -> None:
    # The JSON entrypoint requires a non-empty target string.
    assert parse_action({"type": "insert_node", "subtree": "x", "target": "", "position": "before"}) == SkipReason.MissingRequired


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
    action = AddNodeAction("inserted", LocationAnchor(position="before", target="1.1"))
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
    action = AddNodeAction("inserted", LocationAnchor(position="after", target="1.2"))
    act.check_against_md(input_md, action, expected_md)


# ---------- position=inside ----------


def test_insert_into_empty_leaf_listitem_via_inside() -> None:
    input_md = """- item
"""
    expected_md = """- item

  nested para
"""
    # Leaf ListItem 1.1 has no children — 'inside' is the only way to add a child.
    action = AddNodeAction("nested para", LocationAnchor(position="inside", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_inside_non_empty_container_rejected() -> None:
    # Section 1 already has body content — 'inside' must reject.
    action = AddNodeAction("x", LocationAnchor(position="inside", target="1"))
    act.check_can_apply("# top\n\nbody\n", action, SkipReason.InvalidAnchor)


# ---------- parse_action ----------


def test_parse_action_builds_insert_node_with_string_subtree() -> None:
    result = parse_action({"type": "insert_node", "subtree": "hello", "target": "1.1", "position": "after"})
    assert isinstance(result, AddNodeAction)
    assert result.subtree_raw == "hello"


def test_parse_action_builds_insert_node_with_dict_subtree() -> None:
    result = parse_action(
        {
            "type": "insert_node",
            "subtree": {"node_type": "Paragraph", "text": "x"},
            "target": "1.1",
            "position": "before",
        }
    )
    assert isinstance(result, AddNodeAction)


def test_parse_action_missing_subtree() -> None:
    assert parse_action({"type": "insert_node", "target": "1.1", "position": "after"}) == SkipReason.MissingRequired


def test_parse_action_missing_target() -> None:
    assert parse_action({"type": "insert_node", "subtree": "x", "position": "after"}) == SkipReason.MissingRequired


def test_parse_action_missing_position() -> None:
    assert parse_action({"type": "insert_node", "subtree": "x", "target": "1.1"}) == SkipReason.MissingRequired


def test_parse_action_invalid_position_value() -> None:
    assert parse_action({"type": "insert_node", "subtree": "x", "target": "1", "position": "bogus"}) == SkipReason.MissingRequired


# ---------- Markdown subtree (string payload parsed as markdown) ----------


def test_insert_markdown_section_with_body() -> None:
    input_md = """# foo

intro
"""
    expected_md = """# foo

intro

## bar

in bar
"""
    subtree = "## bar\n\nin bar\n"
    action = AddNodeAction(subtree, LocationAnchor(position="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_markdown_paragraph_with_examples_directive() -> None:
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
    subtree = "new para\n\n::: examples\nan example\n:::\n"
    action = AddNodeAction(subtree, LocationAnchor(position="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_markdown_multi_block_splats() -> None:
    input_md = """# top

intro
"""
    expected_md = """# top

intro

first para

second para
"""
    subtree = "first para\n\nsecond para\n"
    action = AddNodeAction(subtree, LocationAnchor(position="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_markdown_list_into_existing_list_unwraps() -> None:
    # Markdown "- new1\n- new2" parses as List([ListItem, ListItem]).
    # Anchored as a sibling of an existing ListItem, the parent is a List, so
    # the wrapping List is unwrapped and the items splat into the destination.
    input_md = """- a
- b
"""
    expected_md = """- a
- new1
- new2
- b
"""
    subtree = "- new1\n- new2\n"
    action = AddNodeAction(subtree, LocationAnchor(position="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_insert_markdown_heading_without_body_rejected() -> None:
    # `## heading` alone parses to an empty Section — empty-container check fires.
    action = AddNodeAction("## empty heading\n", LocationAnchor(position="after", target="1.1"))
    act.check_can_apply("# top\n\nbody\n", action, SkipReason.InvalidSubtree)


def test_insert_markdown_empty_string_rejected() -> None:
    action = AddNodeAction("   \n\n", LocationAnchor(position="after", target="1.1"))
    act.check_can_apply("# top\n\nbody\n", action, SkipReason.InvalidSubtree)


def test_insert_markdown_paragraph_under_list_rejected() -> None:
    # Parent is List (sibling of existing ListItem). A bare paragraph has no
    # wrap semantics under a List.
    action = AddNodeAction("stray para\n", LocationAnchor(position="after", target="1.1"))
    act.check_can_apply("- a\n- b\n", action, SkipReason.InvalidStructure)


def test_insert_markdown_section_splats_with_following_paragraph() -> None:
    # Multi-root with a Section followed by a trailing paragraph at the
    # document root.
    input_md = """# top

intro
"""
    expected_md = """# top

intro

## bar

in bar

trailer
"""
    subtree = "## bar\n\nin bar\n\ntrailer\n"
    action = AddNodeAction(subtree, LocationAnchor(position="after", target="1.1"))
    act.check_against_md(input_md, action, expected_md)
