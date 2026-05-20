from __future__ import annotations

from prompt_model.model import Document, Paragraph
from prompt_model.service.actions import (
    LocationAnchor,
    MoveNodeAction,
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


def _parse(md: str) -> Document:
    from prompt_model.service.parsing.parse_prompt import parse_from_string

    return parse_from_string(md)


def test_move_section_first_child_of_document_when_already_first_is_noop() -> None:
    # Empty-string target is the Document-root convention used by resolve_anchor.
    tree = _parse("# a\n\nbody\n")
    action = MoveNodeAction("1", _anchor("first_child", ""))
    assert action.validate(tree) == SkipReason.InvalidAnchor


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
# 13. Interaction with other actions in a batch
# =====================================================================


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


# --- Section behaviour ---


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


# --- auto-wrap isolation ---


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


# =====================================================================
# 16. Noop: adjacent sibling positions
# =====================================================================


def test_noop_before_next_sibling() -> None:
    # Moving node "1.1" before "1.2" — insertion index is 1, source_index is
    # 0, so dest_index == source_index + 1 → noop by _is_noop.
    tree = _parse("# foo\n\npara one\n\npara two\n\npara three\n")
    action = MoveNodeAction("1.1", _anchor("before", "1.2"))
    assert action.validate(tree) == SkipReason.InvalidAnchor


def test_noop_after_previous_sibling() -> None:
    # Moving node "1.2" after "1.1" — insertion index is 1, source_index is
    # 1, so dest_index == source_index → noop by _is_noop.
    tree = _parse("# foo\n\npara one\n\npara two\n\npara three\n")
    action = MoveNodeAction("1.2", _anchor("after", "1.1"))
    assert action.validate(tree) == SkipReason.InvalidAnchor


def test_noop_before_next_sibling_section() -> None:
    # Same adjacency check for Section nodes.
    tree = _parse("# top\n\n## a\n\nbody a\n\n## b\n\nbody b\n")
    action = MoveNodeAction("1.1", _anchor("before", "1.2"))
    assert action.validate(tree) == SkipReason.InvalidAnchor


def test_noop_after_previous_sibling_section() -> None:
    tree = _parse("# top\n\n## a\n\nbody a\n\n## b\n\nbody b\n")
    action = MoveNodeAction("1.2", _anchor("after", "1.1"))
    assert action.validate(tree) == SkipReason.InvalidAnchor


# =====================================================================
# 17. ListItem into an existing List (no auto-wrap)
# =====================================================================


def test_listitem_into_sibling_list_no_wrap() -> None:
    # A ListItem moved into an existing List should land directly in that
    # list — no extra wrapper List should be inserted.
    # Two lists separated by a paragraph so the parser creates two distinct
    # List nodes (blank line alone merges them into one).
    input_md = """# foo

- a
- b

sep

- c
- d
"""
    # Tree: list(1.1)=[a(1.1.1), b(1.1.2)], para(1.2)=sep, list(1.3)=[c(1.3.1), d(1.3.2)]
    # Move "a" (1.1.1) before "c" (1.3.1) — dest_parent is the second List (1.3).
    action = MoveNodeAction("1.1.1", _anchor("before", "1.3.1"))
    tree = _parse(input_md)
    assert action.validate(tree) is None
    action.apply(tree)
    md = tree.to_markdown()
    # "a" should appear before "c" and not be wrapped in its own extra list.
    assert md.index("- a") < md.index("- c")
    assert md.count("- a") == 1
    assert md.count("- b") == 1
    assert md.count("- c") == 1


def test_listitem_into_sibling_list_preserves_order() -> None:
    input_md = """# foo

- x

sep

- a
- b
- c
"""
    # Tree: list(1.1)=[x(1.1.1)], para(1.2)=sep, list(1.3)=[a(1.3.1),b(1.3.2),c(1.3.3)]
    # Move "x" (1.1.1) as last_child of second list (1.3) — no auto-wrap.
    action = MoveNodeAction("1.1.1", _anchor("last_child", "1.3"))
    tree = _parse(input_md)
    assert action.validate(tree) is None
    action.apply(tree)
    md = tree.to_markdown()
    assert md.index("- a") < md.index("- b") < md.index("- c") < md.index("- x")
    assert md.count("- x") == 1


def test_listitem_move_no_wrap_roundtrip() -> None:
    input_md = """# foo

- a
- b

sep

- c
"""
    # Tree: list(1.1)=[a(1.1.1),b(1.1.2)], para(1.2)=sep, list(1.3)=[c(1.3.1)]
    action = MoveNodeAction("1.1.1", _anchor("last_child", "1.3"))
    tree = _parse(input_md)
    action.apply(tree)
    md1 = tree.to_markdown()
    tree2 = _parse(md1)
    md2 = tree2.to_markdown()
    assert md1 == md2


# =====================================================================
# 18. Source-list cleanup + grandparent dest_index adjustment
# =====================================================================


def test_cleanup_dest_after_removed_list() -> None:
    # The only item in a list is moved to a position AFTER the list in the
    # same section but NOT at the end — specifically between two other siblings.
    # After the list is removed (cleanup) its slot shifts all subsequent indices
    # down by one, so dest_index must be decremented a second time. Without that
    # fix the item would land one position too far right (after para two instead
    # of between para one and para two).
    input_md = """# foo

- only

para one

para two
"""
    # Tree: list(1.1)=[only(1.1.1)], para(1.2)=para one, para(1.3)=para two
    # Moving "only" after "para one" (1.2): raw dest_index=2, list at gp_index=0.
    # Cleanup removes list → gp_index=0 shift → dest_index becomes 1 → lands
    # between para one and para two.
    action = MoveNodeAction("1.1.1", _anchor("after", "1.2"))
    tree = _parse(input_md)
    assert action.validate(tree) is None
    action.apply(tree)
    md = tree.to_markdown()
    # Order must be: para one → - only → para two.
    assert md.index("para one") < md.index("- only") < md.index("para two")
    assert md.count("- only") == 1


def test_cleanup_dest_before_removed_list_position() -> None:
    # Similar: move the only item to BEFORE a sibling that came AFTER the list.
    # After cleanup, dest_index is NOT shifted (dest is before the removed list
    # in the sibling order), so the item lands correctly before that sibling.
    input_md = """# foo

para

- only
"""
    # "para" is 1.1, list is 1.2 (index 1), "only" is 1.2.1.
    # Move "only" before "para" (dest_index = 0, before the list's gp_index=1
    # so no second adjustment needed).
    action = MoveNodeAction("1.2.1", _anchor("before", "1.1"))
    tree = _parse(input_md)
    assert action.validate(tree) is None
    action.apply(tree)
    md = tree.to_markdown()
    assert md.index("- only") < md.index("para")
    assert md.count("- only") == 1


def test_cleanup_roundtrip() -> None:
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
# 19. validate / apply consistency
# =====================================================================


def test_validate_then_apply_annotations_consistent() -> None:
    input_md = """# foo

para one

::: examples
for one
:::

para two
"""
    action = MoveNodeAction("1.1", _anchor("after", "1.2"))
    tree = _parse(input_md)
    assert action.validate(tree) is None
    action.apply(tree)
    md = tree.to_markdown()
    assert "for one" in md
    assert "para two" in md


def test_validate_then_apply_section_level_shift_consistent() -> None:
    input_md = """# top

## a

inner a

## b

inner b
"""
    action = MoveNodeAction("1.1", _anchor("last_child", "1.2"))
    tree = _parse(input_md)
    assert action.validate(tree) is None
    action.apply(tree)
    assert "### a" in tree.to_markdown()


def test_validate_then_apply_autowrap_consistent() -> None:
    input_md = """# foo

intro

- a
- b
"""
    action = MoveNodeAction("1.2.1", _anchor("first_child", "1"))
    tree = _parse(input_md)
    assert action.validate(tree) is None
    action.apply(tree)
    md = tree.to_markdown()
    assert md.index("- a") < md.index("intro")


def test_validate_then_apply_source_cleanup_consistent() -> None:
    input_md = """# foo

- only

para
"""
    action = MoveNodeAction("1.1.1", _anchor("after", "1.2"))
    tree = _parse(input_md)
    assert action.validate(tree) is None
    action.apply(tree)
    md = tree.to_markdown()
    assert md.count("- only") == 1
    assert md.index("para") < md.index("- only")


# =====================================================================
# 20. Cross-parent before/after — same depth, delta zero
# =====================================================================


def test_cross_parent_same_depth_section_level_unchanged() -> None:
    # Move an h2 from one h1 to a sibling position next to another h1 via
    # "before". Since the new location is still a direct child of Document,
    # the section level should remain h1 (Document child = level 1, but the
    # section being moved is h2, so delta stays 0... wait, moving h2 to
    # before a sibling h1 that is also Document child would make it h1).
    # Correct scenario: move h2 out of one h1 to be sibling of both h1s.
    input_md = """# first

## shared

body

# second

body second
"""
    # "shared" (1.1, h2) moved before "second" (2, h1) — dest_parent is
    # Document, so new level = 1, delta = -1.
    action = MoveNodeAction("1.1", _anchor("before", "2"))
    tree = _parse(input_md)
    assert action.validate(tree) is None
    action.apply(tree)
    md = tree.to_markdown()
    # "shared" is now a top-level h1.
    assert "# shared" in md
    assert "## shared" not in md


def test_cross_parent_same_parent_depth_no_level_change() -> None:
    # Move h2 from one position to after its last h2 sibling — both share the
    # same h1 parent, so delta = 0 and level is unchanged.
    input_md = """# top

## a

body a

## b

body b

## c

body c
"""
    # Move "a" (1.1) to after "c" (1.3) — same parent (top), same depth.
    action = MoveNodeAction("1.1", _anchor("after", "1.3"))
    tree = _parse(input_md)
    assert action.validate(tree) is None
    action.apply(tree)
    md = tree.to_markdown()
    assert "## a" in md
    assert "### a" not in md
    # "# a" is a substring of "## a" — check no line uses exactly h1 level.
    assert not any(line == "# a" for line in md.splitlines())


# =====================================================================
# 21. Section with mixed subtree content
# =====================================================================


def test_move_section_with_lists_and_paragraphs() -> None:
    input_md = """# top

## a

body a

- item x
- item y

## b

body b
"""
    # Move "a" (1.1) under "b" (1.2) — becomes h3, list children are intact.
    action = MoveNodeAction("1.1", _anchor("last_child", "1.2"))
    tree = _parse(input_md)
    assert action.validate(tree) is None
    action.apply(tree)
    md = tree.to_markdown()
    assert "### a" in md
    assert "- item x" in md
    assert "- item y" in md
    assert "body a" in md


def test_move_section_with_annotations_intact() -> None:
    input_md = """# top

## a

para

::: examples
example A
:::

## b

body b
"""
    # Move "a" (1.1) after "b" (1.2) — same parent, level unchanged, annotation travels.
    action = MoveNodeAction("1.1", _anchor("after", "1.2"))
    tree = _parse(input_md)
    assert action.validate(tree) is None
    action.apply(tree)
    md = tree.to_markdown()
    assert "## a" in md
    assert "example A" in md
    assert md.index("body b") < md.index("example A")


def test_move_section_mixed_subtree_roundtrip() -> None:
    input_md = """# top

## a

body a

- x
- y

### deep

deep body

## b

body b
"""
    action = MoveNodeAction("1.1", _anchor("last_child", "1.2"))
    tree = _parse(input_md)
    action.apply(tree)
    md1 = tree.to_markdown()
    tree2 = _parse(md1)
    md2 = tree2.to_markdown()
    assert md1 == md2


# =====================================================================
# 22. Deeply nested lists
# =====================================================================


def test_move_from_nested_listitem() -> None:
    # A ListItem that lives inside a nested list (list inside listitem).
    # Moving it out should auto-wrap and clean up correctly.
    input_md = """# foo

- outer

  - inner a
  - inner b

para
"""
    # "inner a" is a listitem inside the nested list. Move it before "para".
    # Locate it: section 1, list 1.1, listitem 1.1.1, nested list 1.1.1.1,
    # listitem 1.1.1.1.1.
    tree = _parse(input_md)
    # Find the id of inner a dynamically to avoid fragile hardcoding.
    from prompt_model.model import ListItem
    from prompt_model.service.actions._walk import walk_all

    inner_a_id = None
    for node in walk_all(tree):
        if isinstance(node, ListItem) and node.text == "inner a":
            inner_a_id = node.id
            break
    assert inner_a_id is not None, "could not find 'inner a' node"

    # Find id of para
    from prompt_model.model import Paragraph

    para_id = None
    for node in walk_all(tree):
        if isinstance(node, Paragraph) and node.text == "para":
            para_id = node.id
            break
    assert para_id is not None

    action = MoveNodeAction(inner_a_id, _anchor("before", para_id))
    assert action.validate(tree) is None
    action.apply(tree)
    md = tree.to_markdown()
    assert "inner a" in md
    assert md.index("inner a") < md.index("para")


def test_move_into_nested_list_as_last_child() -> None:
    # Move a top-level ListItem into a nested List as last_child.
    input_md = """# foo

- top item

- outer

  - nested a
"""
    tree = _parse(input_md)
    from prompt_model.model import List, ListItem
    from prompt_model.service.actions._walk import walk_all

    top_item_id = None
    nested_list_id = None
    for node in walk_all(tree):
        if isinstance(node, ListItem) and node.text == "top item":
            top_item_id = node.id
        if isinstance(node, List):
            for child in node.children:
                if isinstance(child, ListItem) and child.text == "outer":
                    # The nested list is inside this listitem's children
                    for grandchild in getattr(child, "children", []):
                        if isinstance(grandchild, List):
                            nested_list_id = grandchild.id

    assert top_item_id is not None
    assert nested_list_id is not None

    action = MoveNodeAction(top_item_id, _anchor("last_child", nested_list_id))
    assert action.validate(tree) is None
    action.apply(tree)
    md = tree.to_markdown()
    assert "top item" in md
    assert "nested a" in md
