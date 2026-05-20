from __future__ import annotations

from prompt_model.model import Document, Paragraph
from prompt_model.service.actions import (
    Action,
    AddExampleAction,
    LocationAnchor,
    MoveNodeAction,
    RewriteNodeAction,
    SkipReason,
    parse_action,
)
from prompt_model.service.actions.anchor import AnchorKind

from ..utils import actions as act


def _anchor(kind: AnchorKind, target: str) -> LocationAnchor:
    return LocationAnchor(kind=kind, target=target)


# =====================================================================
# 1. Basic structural moves
# =====================================================================


def test_move_paragraph_before_sibling() -> None:
    input_md = """# foo

para one

para two

para three
"""
    expected_md = """# foo

para three

para one

para two
"""
    action = MoveNodeAction("1.3", _anchor("before", "1.1"))
    act.check_against_md(input_md, action, expected_md)


def test_move_paragraph_across_sections() -> None:
    input_md = """# a

intro a

## b

inner b
"""
    # Move 'intro a' (1.1) into section b as last_child.
    action = MoveNodeAction("1.1", _anchor("last_child", "1.2"))
    act.check_undo(input_md, [action])


def _parse(md: str) -> Document:
    from prompt_model.service.parsing.parse_prompt import parse_from_string

    return parse_from_string(md)


def test_move_section_first_child_of_document_when_already_first_is_noop() -> None:
    # Empty-string target is the Document-root convention used by resolve_anchor.
    tree = _parse("# a\n\nbody\n")
    action = MoveNodeAction("1", _anchor("first_child", ""))
    assert action.validate(tree) == SkipReason.InvalidAnchor


def test_move_second_section_to_first_child_of_document() -> None:
    input_md = """# a

a body

# b

b body
"""
    # Move section b to first_child of Document.
    action = MoveNodeAction("2", _anchor("first_child", ""))
    act.check_undo(input_md, [action])


def test_move_codeblock_after_sibling() -> None:
    input_md = """# foo

para one

```py
x = 1
```

para two
"""
    # Move codeblock (1.2) to after para two (1.3).
    action = MoveNodeAction("1.2", _anchor("after", "1.3"))
    act.check_undo(input_md, [action])


def test_move_blockquote_into_other_section() -> None:
    input_md = """# a

> quoted

## b

inner
"""
    action = MoveNodeAction("1.1", _anchor("last_child", "1.2"))
    act.check_undo(input_md, [action])


def test_move_table_reordered_among_siblings() -> None:
    input_md = """# foo

para one

| a | b |
|---|---|
| 1 | 2 |

para two
"""
    # Move table (1.2) to first child of section.
    action = MoveNodeAction("1.2", _anchor("first_child", "1"))
    act.check_undo(input_md, [action])


# =====================================================================
# 2. Subtree integrity — children come along
# =====================================================================


def test_move_section_carries_nested_sections() -> None:
    input_md = """# top

## a

inner a

### a1

deep a1

## b

inner b
"""
    # Move section a (1.1) to after section b (1.2).
    action = MoveNodeAction("1.1", _anchor("after", "1.2"))
    act.check_undo(input_md, [action])


def test_move_list_carries_all_items() -> None:
    input_md = """# foo

intro

- a
- b
- c
"""
    # Move list before intro.
    action = MoveNodeAction("1.2", _anchor("before", "1.1"))
    act.check_undo(input_md, [action])


def test_move_listitem_with_block_children() -> None:
    input_md = """# foo

- top item

  nested paragraph

  - nested list a
  - nested list b
- sibling
"""
    # Move the item with nested children to after its sibling.
    action = MoveNodeAction("1.1.1", _anchor("after", "1.1.2"))
    act.check_undo(input_md, [action])


# =====================================================================
# 3. Annotation groups travel with host
# =====================================================================


def test_move_paragraph_with_examples_carries_them() -> None:
    input_md = """# foo

para one

::: examples
ex
:::

para two
"""
    # Move para one to after para two — examples should land at the end.
    action = MoveNodeAction("1.1", _anchor("after", "1.2"))
    act.check_undo(input_md, [action])


def test_move_paragraph_with_guidance_carries_it() -> None:
    input_md = """# foo

para one

::: guidance
be precise
:::

para two
"""
    action = MoveNodeAction("1.1", _anchor("after", "1.2"))
    act.check_undo(input_md, [action])


def test_move_paragraph_with_both_groups_carries_both() -> None:
    input_md = """# foo

para one

::: examples
ex
:::

::: guidance
be precise
:::

para two
"""
    action = MoveNodeAction("1.1", _anchor("after", "1.2"))
    act.check_undo(input_md, [action])


def test_move_listitem_with_annotations_within_list() -> None:
    input_md = """# foo

- a

  ::: examples
  ex for a
  :::
- b
"""
    action = MoveNodeAction("1.1.1", _anchor("after", "1.1.2"))
    act.check_undo(input_md, [action])


def test_move_listitem_with_annotations_to_section_auto_wraps() -> None:
    input_md = """# foo

- a

  ::: examples
  ex
  :::
- b
"""
    # Move 'a' to be first child of section; it auto-wraps in a new list
    # and brings its examples along.
    action = MoveNodeAction("1.1.1", _anchor("first_child", "1"))
    act.check_undo(input_md, [action])


def test_move_does_not_cross_pollinate_annotations() -> None:
    input_md = """# foo

para one

::: examples
for one
:::

para two

::: examples
for two
:::
"""
    # Move para one to after para two; each paragraph keeps its own example.
    action = MoveNodeAction("1.1", _anchor("after", "1.2"))
    tree = _parse(input_md)
    action.apply(tree)
    md = tree.to_markdown()
    # 'for one' should appear after 'for two' (since para one is now last).
    assert md.index("for two") < md.index("for one")


# =====================================================================
# 4. Section level adjustment
# =====================================================================


def test_move_section_h2_stays_h2_under_h1() -> None:
    input_md = """# top

## a

inner a

## b

inner b
"""
    # Move a after b — same parent, level unchanged.
    action = MoveNodeAction("1.1", _anchor("after", "1.2"))
    tree = _parse(input_md)
    action.apply(tree)
    assert "## a" in tree.to_markdown()


def test_move_section_h2_into_h2_becomes_h3() -> None:
    input_md = """# top

## a

inner a

## b

inner b
"""
    # Move a as last_child of b — a becomes h3.
    action = MoveNodeAction("1.1", _anchor("last_child", "1.2"))
    tree = _parse(input_md)
    action.apply(tree)
    md = tree.to_markdown()
    assert "### a" in md


def test_move_section_h3_to_document_becomes_h1() -> None:
    input_md = """# top

## mid

### deep

deep body
"""
    # Move 'deep' (1.1.1) to be last_child of Document (sibling of top).
    action = MoveNodeAction("1.1.1", _anchor("last_child", ""))
    tree = _parse(input_md)
    action.apply(tree)
    md = tree.to_markdown()
    # 'deep' should now be at the top level.
    assert "\n# deep" in md or md.startswith("# top") and "# deep" in md


def test_move_section_with_children_shifts_subtree_levels() -> None:
    input_md = """# top

## a

inner a

### a1

deep a1

## b

inner b
"""
    # Move 'a' under 'b' — a becomes h3, a1 becomes h4.
    action = MoveNodeAction("1.1", _anchor("last_child", "1.2"))
    tree = _parse(input_md)
    action.apply(tree)
    md = tree.to_markdown()
    assert "### a" in md
    assert "#### a1" in md


def test_move_section_that_would_exceed_h6_skips() -> None:
    input_md = """# top

## donor

body donor

# other

## a

### b

#### c

##### d

###### e

body e
"""
    # Move 'donor' (1.1, h2) under 'e' (2.1.1.1.1.1, h6 in a different
    # branch — no cycle). Donor would need to become h7 — invalid. Skip.
    action = MoveNodeAction("1.1", _anchor("last_child", "2.1.1.1.1.1"))
    tree = _parse(input_md)
    assert action.validate(tree) == SkipReason.InvalidStructure


def test_move_section_round_trip_restores_levels() -> None:
    input_md = """# top

## a

inner

### a1

inner a1

## b

inner b
"""
    action = MoveNodeAction("1.1", _anchor("last_child", "1.2"))
    act.check_undo(input_md, [action])


# =====================================================================
# 5. ListItem auto-wrap
# =====================================================================


def test_auto_wrap_inherits_unordered() -> None:
    input_md = """# foo

intro

- a
- b
"""
    action = MoveNodeAction("1.2.1", _anchor("first_child", "1"))
    tree = _parse(input_md)
    action.apply(tree)
    md = tree.to_markdown()
    # New list at top of section is unordered.
    assert md.index("- a") < md.index("intro")


def test_auto_wrap_inherits_ordered() -> None:
    input_md = """# foo

intro

1. a
2. b
"""
    action = MoveNodeAction("1.2.1", _anchor("first_child", "1"))
    tree = _parse(input_md)
    action.apply(tree)
    md = tree.to_markdown()
    # New list at top of section preserves ordered marker.
    assert "1. a" in md
    assert md.index("1. a") < md.index("intro")


def test_auto_wrap_carries_annotations() -> None:
    input_md = """# foo

intro

- a

  ::: examples
  ex
  :::
- b
"""
    action = MoveNodeAction("1.2.1", _anchor("first_child", "1"))
    act.check_undo(input_md, [action])


def test_auto_wrap_carries_block_children() -> None:
    input_md = """# foo

intro

- top

  nested para inside item
- sibling
"""
    action = MoveNodeAction("1.2.1", _anchor("first_child", "1"))
    act.check_undo(input_md, [action])


def test_listitem_to_existing_list_no_wrap() -> None:
    input_md = """# foo

- a
- b

para

- c
- d
"""
    # Move 'a' (1.1.1) to after 'd' (1.3.2) — both contexts are Lists, no wrap.
    action = MoveNodeAction("1.1.1", _anchor("after", "1.3.2"))
    act.check_undo(input_md, [action])


# =====================================================================
# 6. Source-list cleanup
# =====================================================================


def test_move_only_listitem_removes_source_list() -> None:
    input_md = """# foo

intro

- only
"""
    action = MoveNodeAction("1.2.1", _anchor("before", "1.1"))
    tree = _parse(input_md)
    action.apply(tree)
    md = tree.to_markdown()
    # 'intro' remains, 'only' moved to before it (wrapped in fresh list);
    # original source list is gone (only one '- only' line, before intro).
    assert md.count("- only") == 1
    assert md.index("- only") < md.index("intro")


def test_move_only_listitem_round_trips() -> None:
    input_md = """# foo

intro

- only
"""
    action = MoveNodeAction("1.2.1", _anchor("before", "1.1"))
    act.check_undo(input_md, [action])


def test_move_one_of_many_keeps_source_list() -> None:
    input_md = """# foo

- a
- b

para
"""
    # Move 'a' to last_child of section; list still has 'b'.
    action = MoveNodeAction("1.1.1", _anchor("last_child", "1"))
    tree = _parse(input_md)
    action.apply(tree)
    md = tree.to_markdown()
    assert "- b" in md
    # Both 'a' and 'b' appear once.
    assert md.count("- a") == 1
    assert md.count("- b") == 1


def test_move_only_listitem_cleanup_shifts_dest_index() -> None:
    # Exercises the dest_index decrement when source-list cleanup pops a
    # sibling that lay BEFORE the destination index in the same parent.
    input_md = """# foo

- only

para tail
"""
    # Source list at 1.1, source listitem at 1.1.1. Move it to last_child of
    # section 1. Pre-lift, section children are [list, para_tail]. After
    # cleanup removes the now-empty list (index 0), 'para tail' shifts to
    # index 0; dest_index was 2 (after both), needs to become 1.
    action = MoveNodeAction("1.1.1", _anchor("last_child", "1"))
    act.check_undo(input_md, [action])


def test_move_deep_listitem_round_trips() -> None:
    input_md = """# foo

- outer

  - inner
- sibling
"""
    # Move 'inner' (deep nested listitem) to be last_child of the section.
    # The inner list becomes empty and is cleaned up.
    action = MoveNodeAction("1.1.1.1.1", _anchor("last_child", "1"))
    act.check_undo(input_md, [action])


# =====================================================================
# 7. Same-parent reordering
# =====================================================================


def test_same_parent_first_to_last() -> None:
    input_md = """# foo

para one

para two

para three
"""
    # Move para one to after para three.
    action = MoveNodeAction("1.1", _anchor("after", "1.3"))
    expected_md = """# foo

para two

para three

para one
"""
    act.check_against_md(input_md, action, expected_md)


def test_same_parent_last_to_first() -> None:
    input_md = """# foo

para one

para two

para three
"""
    action = MoveNodeAction("1.3", _anchor("before", "1.1"))
    expected_md = """# foo

para three

para one

para two
"""
    act.check_against_md(input_md, action, expected_md)


def test_same_parent_middle_to_middle_round_trip() -> None:
    input_md = """# foo

a

b

c

d

e
"""
    # b → between d and e.
    action = MoveNodeAction("1.2", _anchor("after", "1.4"))
    act.check_undo(input_md, [action])


def test_same_list_reorder_round_trip() -> None:
    input_md = """# foo

1. a
2. b
3. c
"""
    # Move 'a' to after 'c'.
    action = MoveNodeAction("1.1.1", _anchor("after", "1.1.3"))
    act.check_undo(input_md, [action])


# =====================================================================
# 8. No-op detection
# =====================================================================


def test_noop_after_self() -> None:
    tree = _parse("# foo\n\npara one\n\npara two\n")
    action = MoveNodeAction("1.1", _anchor("after", "1.1"))
    assert action.validate(tree) == SkipReason.InvalidAnchor


def test_noop_before_self() -> None:
    tree = _parse("# foo\n\npara one\n\npara two\n")
    action = MoveNodeAction("1.1", _anchor("before", "1.1"))
    assert action.validate(tree) == SkipReason.InvalidAnchor


def test_noop_first_child_when_already_first() -> None:
    tree = _parse("# foo\n\npara one\n\npara two\n")
    action = MoveNodeAction("1.1", _anchor("first_child", "1"))
    assert action.validate(tree) == SkipReason.InvalidAnchor


def test_noop_last_child_when_already_last() -> None:
    tree = _parse("# foo\n\npara one\n\npara two\n")
    action = MoveNodeAction("1.2", _anchor("last_child", "1"))
    assert action.validate(tree) == SkipReason.InvalidAnchor


def test_first_child_when_not_first_is_real_move() -> None:
    tree = _parse("# foo\n\npara one\n\npara two\n")
    action = MoveNodeAction("1.2", _anchor("first_child", "1"))
    assert action.validate(tree) is None


# =====================================================================
# 9. Cycle detection
# =====================================================================


def test_cycle_section_into_own_descendant() -> None:
    input_md = """# top

## inner

deep body
"""
    tree = _parse(input_md)
    action = MoveNodeAction("1", _anchor("last_child", "1.1"))
    assert action.validate(tree) == SkipReason.InvalidAnchor


def test_cycle_list_after_own_listitem() -> None:
    input_md = """# foo

- a
- b
"""
    tree = _parse(input_md)
    # Try to move the list (1.1) to after one of its own items (1.1.1).
    action = MoveNodeAction("1.1", _anchor("after", "1.1.1"))
    assert action.validate(tree) == SkipReason.InvalidAnchor


def test_cycle_first_child_of_self() -> None:
    input_md = """# top

## inner

body
"""
    tree = _parse(input_md)
    # first_child of self — the parent resolved is the node itself.
    action = MoveNodeAction("1", _anchor("first_child", "1"))
    assert action.validate(tree) == SkipReason.InvalidAnchor


# =====================================================================
# 10. Illegal target / structural skips
# =====================================================================


def test_annotation_id_skipped() -> None:
    input_md = """# foo

para

::: examples
ex
:::
"""
    tree = _parse(input_md)
    action = MoveNodeAction("1.1.e1", _anchor("last_child", "1"))
    assert action.validate(tree) == SkipReason.TargetNotFound


def test_missing_id_skipped() -> None:
    tree = _parse("# foo\n\npara\n")
    action = MoveNodeAction("9.9", _anchor("last_child", "1"))
    assert action.validate(tree) == SkipReason.TargetNotFound


def test_paragraph_into_list_skipped() -> None:
    input_md = """# foo

para

- a
"""
    tree = _parse(input_md)
    action = MoveNodeAction("1.1", _anchor("last_child", "1.2"))
    assert action.validate(tree) == SkipReason.InvalidStructure


def test_section_into_listitem_skipped() -> None:
    input_md = """# top

intro

- item
"""
    tree = _parse(input_md)
    # Top section into listitem inside it — also a cycle, but either skip
    # reason is acceptable.
    action = MoveNodeAction("1", _anchor("last_child", "1.2.1"))
    assert action.validate(tree) in (SkipReason.InvalidAnchor, SkipReason.InvalidStructure)


def test_codeblock_into_list_skipped() -> None:
    input_md = """# foo

```py
x = 1
```

- a
"""
    tree = _parse(input_md)
    action = MoveNodeAction("1.1", _anchor("last_child", "1.2"))
    assert action.validate(tree) == SkipReason.InvalidStructure


def test_invalid_anchor_target_skipped() -> None:
    tree = _parse("# foo\n\npara\n")
    action = MoveNodeAction("1.1", _anchor("after", "9.9"))
    assert action.validate(tree) == SkipReason.InvalidAnchor


# =====================================================================
# 11. Malformed action JSON
# =====================================================================


def test_parse_move_node_well_formed() -> None:
    result = parse_action({"type": "move_node", "id": "1.1", "anchor": {"after": "1.2"}})
    assert isinstance(result, MoveNodeAction)
    assert result.node_id == "1.1"
    assert result.anchor.kind == "after"
    assert result.anchor.target == "1.2"


def test_parse_move_node_missing_id() -> None:
    result = parse_action({"type": "move_node", "anchor": {"after": "1.2"}})
    assert result == SkipReason.MissingRequired


def test_parse_move_node_missing_anchor() -> None:
    result = parse_action({"type": "move_node", "id": "1.1"})
    assert result == SkipReason.MissingRequired


def test_parse_move_node_anchor_not_dict() -> None:
    result = parse_action({"type": "move_node", "id": "1.1", "anchor": "after 1.2"})
    assert result == SkipReason.MissingRequired


def test_parse_move_node_unknown_anchor_key() -> None:
    result = parse_action({"type": "move_node", "id": "1.1", "anchor": {"sibling": "1.2"}})
    assert result == SkipReason.MissingRequired


def test_parse_move_node_extra_fields_ignored() -> None:
    result = parse_action(
        {
            "type": "move_node",
            "id": "1.1",
            "anchor": {"after": "1.2"},
            "extra": "ignored",
        }
    )
    assert isinstance(result, MoveNodeAction)


def test_parse_move_node_empty_id() -> None:
    result = parse_action({"type": "move_node", "id": "", "anchor": {"after": "1.2"}})
    assert result == SkipReason.MissingRequired


# =====================================================================
# 12. Undo / round-trip
# =====================================================================


def test_undo_section_move_restores_levels() -> None:
    input_md = """# top

## a

inner a

## b

inner b
"""
    action = MoveNodeAction("1.1", _anchor("last_child", "1.2"))
    act.check_undo(input_md, [action])


def test_undo_listitem_autowrap_removes_wrap() -> None:
    input_md = """# foo

intro

- a
- b
"""
    action = MoveNodeAction("1.2.1", _anchor("first_child", "1"))
    act.check_undo(input_md, [action])


def test_undo_cleanup_recreates_source_list() -> None:
    input_md = """# foo

- only

para
"""
    action = MoveNodeAction("1.1.1", _anchor("after", "1.2"))
    act.check_undo(input_md, [action])


def test_undo_multi_action_batch() -> None:
    input_md = """# foo

para one

para two

para three
"""
    actions: list[Action] = [
        MoveNodeAction("1.1", _anchor("after", "1.3")),
        MoveNodeAction("1.2", _anchor("before", "1.1")),
    ]
    act.check_undo(input_md, actions)


def test_undo_mixed_action_batch() -> None:
    input_md = """# foo

para one

para two
"""
    actions: list[Action] = [
        MoveNodeAction("1.1", _anchor("after", "1.2")),
        RewriteNodeAction("1.2", "rewritten"),
        AddExampleAction("1.2", "an example"),
    ]
    act.check_undo(input_md, actions)


# =====================================================================
# 13. Interaction with other actions in a batch
# =====================================================================


def test_batch_move_then_add_example_resolves_against_snapshot() -> None:
    # IDs resolve against the snapshot the actor saw — but our tests run
    # actions sequentially against the (mutated) tree, so the host id for
    # the AddExample must still exist after the move. Since move_node
    # preserves the node's id, this works.
    input_md = """# foo

para one

para two
"""
    actions: list[Action] = [
        MoveNodeAction("1.1", _anchor("after", "1.2")),
        AddExampleAction("1.1", "post-move example"),
    ]
    act.check_undo(input_md, actions)


def test_batch_move_then_delete_sibling() -> None:
    from prompt_model.service.actions import RemoveNodeAction

    input_md = """# foo

para one

para two

para three
"""
    actions: list[Action] = [
        MoveNodeAction("1.1", _anchor("after", "1.3")),
        RemoveNodeAction("1.2"),
    ]
    act.check_undo(input_md, actions)


def test_batch_two_moves_referencing_snapshot_ids() -> None:
    input_md = """# foo

a

b

c
"""
    # First move a to end; second move b to beginning. After first move,
    # b still has its original id 1.2 (apply doesn't reassign mid-batch).
    actions: list[Action] = [
        MoveNodeAction("1.1", _anchor("after", "1.3")),
        MoveNodeAction("1.2", _anchor("before", "1.3")),
    ]
    act.check_undo(input_md, actions)


# =====================================================================
# 14. Round-trip equivalence via markdown
# =====================================================================


def test_roundtrip_paragraph_move() -> None:
    input_md = """# foo

a

b
"""
    action = MoveNodeAction("1.1", _anchor("after", "1.2"))
    tree = _parse(input_md)
    action.apply(tree)
    md1 = tree.to_markdown()
    # Re-parse and re-render — structure must round-trip cleanly.
    tree2 = _parse(md1)
    md2 = tree2.to_markdown()
    assert md1 == md2


def test_roundtrip_section_level_shift() -> None:
    input_md = """# top

## a

inner

## b

inner b
"""
    action = MoveNodeAction("1.1", _anchor("last_child", "1.2"))
    tree = _parse(input_md)
    action.apply(tree)
    md1 = tree.to_markdown()
    tree2 = _parse(md1)
    md2 = tree2.to_markdown()
    assert md1 == md2


def test_roundtrip_listitem_autowrap() -> None:
    input_md = """# foo

intro

- a
- b
"""
    action = MoveNodeAction("1.2.1", _anchor("first_child", "1"))
    tree = _parse(input_md)
    action.apply(tree)
    md1 = tree.to_markdown()
    tree2 = _parse(md1)
    md2 = tree2.to_markdown()
    assert md1 == md2


def test_roundtrip_source_list_cleanup() -> None:
    input_md = """# foo

- only

para
"""
    action = MoveNodeAction("1.1.1", _anchor("after", "1.2"))
    tree = _parse(input_md)
    action.apply(tree)
    md1 = tree.to_markdown()
    tree2 = _parse(md1)
    md2 = tree2.to_markdown()
    assert md1 == md2


# =====================================================================
# 15. Coverage gaps — added after initial review
# =====================================================================


# --- moves of node types we underexercised ---


def test_move_whole_list_between_sections() -> None:
    input_md = """# a

- x
- y

# b

para b
"""
    # Move the entire List (with both items) from section a into section b.
    action = MoveNodeAction("1.1", _anchor("last_child", "2"))
    act.check_undo(input_md, [action])


def test_move_list_into_listitem_as_nested() -> None:
    input_md = """# foo

- host

- a
- b
"""
    # ListItem.children allows List, so this is a legal direct insertion
    # — but wait, the list to move is `1.1` (single list containing host/a/b).
    # Re-shape: use a list and a separate paragraph-then-list to get two
    # distinct lists.
    input_md = """# foo

- host

para sep

- a
- b
"""
    # Move list 1.3 (a, b) to be a child of listitem 1.1.1 ('host').
    action = MoveNodeAction("1.3", _anchor("last_child", "1.1.1"))
    act.check_undo(input_md, [action])


def test_move_paragraph_directly_under_document() -> None:
    # Paragraph CAN be a direct child of Document (no Section wrapper).
    input_md = """preamble

# foo

body
"""
    # Move 'body' (1.1) to be first_child of Document — alongside the preamble.
    action = MoveNodeAction("2.1", _anchor("first_child", ""))
    act.check_undo(input_md, [action])


def test_move_codeblock_preserves_info_string() -> None:
    input_md = """# foo

para

```python
x = 1
```
"""
    action = MoveNodeAction("1.2", _anchor("before", "1.1"))
    tree = _parse(input_md)
    action.apply(tree)
    md = tree.to_markdown()
    # The info string 'python' survives the move.
    assert "```python" in md


def test_move_table_preserves_content() -> None:
    input_md = """# foo

| a | b |
|---|---|
| 1 | 2 |

para
"""
    action = MoveNodeAction("1.1", _anchor("after", "1.2"))
    tree = _parse(input_md)
    action.apply(tree)
    md = tree.to_markdown()
    assert "| a | b |" in md
    assert "| 1 | 2 |" in md


# --- ListItem ↔ ListItem auto-wrap target ---


def test_move_listitem_to_another_listitem_wraps_in_inner_list() -> None:
    input_md = """# foo

- host

- a
- b
"""
    # Reshape to two distinct lists.
    input_md = """# foo

- host

para sep

- a
- b
"""
    # Move 'a' to be first_child of listitem 'host' (1.1.1). ListItem can
    # carry block children including List, so the moved item auto-wraps in
    # a fresh List nested inside the host item.
    action = MoveNodeAction("1.3.1", _anchor("first_child", "1.1.1"))
    act.check_undo(input_md, [action])


# --- Section behaviour ---


def test_section_emptied_by_move_is_still_valid() -> None:
    # Sections are allowed to be empty (placeholder headings); validation
    # does not reject them. Verifying the move succeeds when it empties a
    # source Section.
    input_md = """# a

## donor

only child para

# b

body b
"""
    # Move 'only child para' (1.1.1) into section b. Section 'donor' (1.1)
    # is left empty but valid.
    action = MoveNodeAction("1.1.1", _anchor("last_child", "2"))
    act.check_undo(input_md, [action])


def test_section_h4_to_document_shifts_delta_minus_three() -> None:
    input_md = """# l1

## l2

### l3

#### donor

donor body

### sibling

sibling body
"""
    # Move 'donor' (h4) to last_child of Document — should become h1 (delta = -3).
    action = MoveNodeAction("1.1.1.1", _anchor("last_child", ""))
    tree = _parse(input_md)
    action.apply(tree)
    md = tree.to_markdown()
    # 'donor' is now a top-level heading.
    assert "\n# donor" in md
    # And re-applying inverse restores h4.
    tree2 = _parse(input_md)
    inv = MoveNodeAction("1.1.1.1", _anchor("last_child", "")).apply(tree2)
    assert not isinstance(inv, list)
    inverse_action: Action = inv
    inverse_action.apply(tree2)
    assert "#### donor" in tree2.to_markdown()


def test_section_level_delta_zero_no_change() -> None:
    # Move a Section to a position where its computed level equals its
    # current level — the level field is not spuriously shifted.
    input_md = """# top

## a

inner a

## b

inner b
"""
    action = MoveNodeAction("1.1", _anchor("after", "1.2"))
    tree = _parse(input_md)
    action.apply(tree)
    md = tree.to_markdown()
    assert "## a" in md
    assert "### a" not in md
    assert "# a" not in md.replace("## a", "")


# --- annotation-heavy scenarios ---


def test_multiline_annotation_text_survives_move() -> None:
    input_md = """# foo

para one

::: examples
first line of example

second line of example
:::

para two
"""
    action = MoveNodeAction("1.1", _anchor("after", "1.2"))
    act.check_undo(input_md, [action])


def test_multiple_annotations_in_group_preserve_order() -> None:
    input_md = """# foo

para one

::: examples
- first
- second
- third
:::

para two
"""
    action = MoveNodeAction("1.1", _anchor("after", "1.2"))
    tree = _parse(input_md)
    action.apply(tree)
    md = tree.to_markdown()
    # Order of examples must be first → second → third post-move.
    assert md.index("first") < md.index("second") < md.index("third")


def test_move_between_two_annotated_hosts() -> None:
    input_md = """# foo

host A

::: examples
ex for A
:::

mover

host B

::: examples
ex for B
:::
"""
    # Move 'mover' (1.2) to after host B (1.3). Annotated hosts on either
    # side must remain unaffected.
    action = MoveNodeAction("1.2", _anchor("after", "1.3"))
    act.check_undo(input_md, [action])


# --- adjacency / spacing in output ---


def test_move_creates_adjacent_annotated_hosts() -> None:
    # After the move, two paragraphs with examples sit next to each other.
    # The generator must still emit blank-line separation between them so
    # the directives re-attach to the correct host on re-parse.
    input_md = """# foo

host A

::: examples
for A
:::

middle

host B

::: examples
for B
:::
"""
    # Move 'middle' (1.2) to first_child of section, leaving A and B adjacent.
    action = MoveNodeAction("1.2", _anchor("first_child", "1"))
    tree = _parse(input_md)
    action.apply(tree)
    md = tree.to_markdown()
    # Re-parse to confirm both annotations attached correctly.
    tree2 = _parse(md)
    md2 = tree2.to_markdown()
    assert md == md2
    assert "for A" in md and "for B" in md


# --- batch / ID semantics ---


def test_moved_node_retains_id_within_batch() -> None:
    # ApplyContext does not re-assign IDs mid-batch. The moved node must
    # keep its original id so subsequent actions in the batch can target it.
    from prompt_model._protocols.action import ApplyContext

    tree = _parse("# foo\n\npara one\n\npara two\n")
    ctx = ApplyContext.from_tree(tree)
    MoveNodeAction("1.1", _anchor("after", "1.2")).apply(tree, ctx)
    # The 'para one' node still has id '1.1' even though it's now in
    # position 2.
    from prompt_model.service.actions._walk import find_node_by_id

    node = find_node_by_id(tree, "1.1")
    assert node is not None
    assert isinstance(node, Paragraph)
    assert node.text == "para one"


def test_three_step_move_chain_and_undo() -> None:
    input_md = """# foo

a

b

c

d
"""
    # a → after b → after c → after d. Then undo back through all three.
    actions: list[Action] = [
        MoveNodeAction("1.1", _anchor("after", "1.2")),
        MoveNodeAction("1.1", _anchor("after", "1.3")),
        MoveNodeAction("1.1", _anchor("after", "1.4")),
    ]
    act.check_undo(input_md, actions)


# --- deeper cycle detection ---


def test_cycle_deep_descendant() -> None:
    input_md = """# top

## mid

### deep

deepest body
"""
    tree = _parse(input_md)
    # Move 'top' (1) under 'deep' (1.1.1) — two levels deep.
    action = MoveNodeAction("1", _anchor("last_child", "1.1.1"))
    assert action.validate(tree) == SkipReason.InvalidAnchor


def test_cycle_via_before_descendant() -> None:
    input_md = """# top

## a

inner a

## b

inner b
"""
    tree = _parse(input_md)
    # Move 'top' (1) before its child 'a' (1.1) — would place top into its
    # own child's slot in section 1. Parent resolved is section 1 itself,
    # which IS the moved node → cycle.
    action = MoveNodeAction("1", _anchor("before", "1.1"))
    assert action.validate(tree) == SkipReason.InvalidAnchor


# --- empty source/target containers ---


def test_move_into_empty_section() -> None:
    # An empty Section is valid markdown (placeholder heading). Verify we
    # can move content into it.
    input_md = """# top

## empty

# other

para to move
"""
    # Move 'para to move' (2.1) into section 'empty' (1.1).
    action = MoveNodeAction("2.1", _anchor("last_child", "1.1"))
    act.check_undo(input_md, [action])


# --- auto-wrap isolation ---


def test_undo_preserves_source_list_ordered_across_unordered_to_ordered_move() -> None:
    # Regression: seed=1102855868 from test_random_long_undo_sequences.
    # The only ListItem of an *unordered* List was moved into an *ordered*
    # List. The source list was cleaned up, but the simple MoveNode inverse
    # picked up `ordered` from the inverse's source_parent — which is the
    # ORDERED destination List — so undo re-created an *ordered* wrapping
    # list at the source slot, losing the original `ordered=False`.
    # The fix is a compound inverse that captures the original source List
    # (with its `ordered` flag) before any mutation.
    input_md = """# foo

intro

- only

para tail

1. other a
2. other b
"""
    # Source: List 1.2 (unordered) with one item 1.2.1 ('only').
    # Destination: into ordered List 1.4 (after item 'other a' at 1.4.1).
    action = MoveNodeAction("1.2.1", _anchor("after", "1.4.1"))
    act.check_undo(input_md, [action])


def test_undo_preserves_source_list_id_across_cleanup_with_wrap() -> None:
    # Regression: seed=1876018022 from test_random_long_undo_sequences.
    # Forward action [1] inserted a paragraph after List "1" (the only
    # List). Action [4] moved the List's only ListItem to a non-List
    # parent (between Document children) — cleanup + auto-wrap fired.
    # The previous fix used a simple MoveNode inverse in the wrap case,
    # which produced an *anonymous* wrap List at the gp slot instead of
    # restoring the original List with id="1". A later inverse in the
    # batch referenced id "1" and failed with `assert source is not None`.
    # The fix uses the compound _CleanupInverse for both cleanup branches.
    from prompt_model.service.actions import RemoveNodeAction

    input_md = """1. only

para tail
"""
    # Two-step batch:
    # [0] move ListItem "1.1" between Document children — triggers
    #     cleanup + wrap. The list "1" gets destroyed.
    # [1] delete the paragraph by id "2". When undoing in LIFO order,
    #     [1]-undo re-inserts the paragraph (fine), then [0]-undo MUST
    #     restore List with id="1" (so the structural state matches).
    # Even without action [1], the inverse must restore List "1" verbatim
    # so any subsequent reference to id "1" resolves.
    actions: list[Action] = [
        MoveNodeAction("1.1", _anchor("after", "2")),
        RemoveNodeAction("2"),
    ]
    act.check_undo(input_md, actions)


def test_undo_preserves_source_list_ordered_across_ordered_to_unordered_move() -> None:
    # Symmetric regression: ordered → unordered list, same risk that the
    # simple inverse would inherit the wrong `ordered`.
    input_md = """# foo

intro

1. only

para tail

- other a
- other b
"""
    action = MoveNodeAction("1.2.1", _anchor("after", "1.4.1"))
    act.check_undo(input_md, [action])


def test_autowrap_does_not_swallow_neighbours() -> None:
    # When a ListItem auto-wraps on landing, the new List contains only
    # the moved item — neighbouring siblings in the destination are not
    # absorbed into it.
    input_md = """# foo

intro

- a
- b
"""
    action = MoveNodeAction("1.2.1", _anchor("after", "1.1"))
    tree = _parse(input_md)
    action.apply(tree)
    md = tree.to_markdown()
    # Expect: 'intro' then a list containing 'a', then a list containing 'b'.
    # The new wrap list around 'a' must not absorb 'intro' or the original
    # list still holding 'b'.
    # Specifically: 'intro' should still be a plain paragraph, not a list item.
    assert "\nintro\n" in md
    assert md.count("- a") == 1
    assert md.count("- b") == 1
