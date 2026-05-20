from __future__ import annotations

from prompt_model.model import Paragraph, Section
from prompt_model.service.actions import (
    AddExampleAction,
    AddGuidanceAction,
    SkipReason,
    parse_action,
)
from prompt_model.service.actions.anchor import LocationAnchor
from prompt_model.service.parsing.parse_prompt import parse_from_string

from ..utils._short_hand import doc_from_shorthand
from ..utils.actions import Action, check_against_md, check_can_apply, check_undo, check_undo_from_sh


def test_simple_add_example() -> None:
    input_md: str = """# foo
test test test
"""
    expected_md: str = """# foo

test test test

::: examples
a small dog
:::
"""
    action: Action = AddExampleAction("1.1", "a small dog", None)
    check_against_md(input_md, action, expected_md)


def test_simple_add_guidance() -> None:
    input_md: str = """# foo
test test test
"""
    expected_md: str = """# foo

test test test

::: guidance
a small dog
:::
"""
    action: Action = AddGuidanceAction("1.1", "a small dog", None)
    check_against_md(input_md, action, expected_md)


def test_add_example_to_existing() -> None:
    input_md: str = """# foo
test test test

::: examples
a big dog
:::
"""
    expected_md: str = """# foo

test test test

::: examples
- a big dog
- a small dog
:::
"""
    action: Action = AddExampleAction("1.1", "a small dog", None)
    check_against_md(input_md, action, expected_md)


def test_add_guidance_to_existing() -> None:
    input_md: str = """# foo
test test test

::: guidance
a big dog
:::
"""
    expected_md: str = """# foo

test test test

::: guidance
- a big dog
- a small dog
:::
"""
    action: Action = AddGuidanceAction("1.1", "a small dog", None)
    check_against_md(input_md, action, expected_md)


def test_add_example_with_existing_guidance() -> None:
    input_md: str = """# foo
test test test

::: guidance
a big dog
:::
"""
    expected_md: str = """# foo

test test test

::: examples
a small dog
:::

::: guidance
a big dog
:::
"""
    action: Action = AddExampleAction("1.1", "a small dog", None)
    check_against_md(input_md, action, expected_md)


# ---------- validate(): fixtures and tests ----------

_DOC_WITH_BOTH = "# Title\n\nBody paragraph.\n\n::: examples\nex one\n:::\n\n::: guidance\ng one\n:::\n"

_DOC_WITH_MULTI = "# Title\n\nBody paragraph.\n\n::: examples\n- e first\n- e second\n:::\n\n::: guidance\n- g first\n- g second\n:::\n"

_DOC_NO_ANNOTATIONS = "# Title\n\nBody paragraph.\n"

_DOC_LIST_HOST = "# Title\n\n- item one\n\n  ::: examples\n  on item\n  :::\n"

_DOC_NESTED = "# Title\n\n## Sub\n\nNested paragraph.\n"


# ---------- text content ----------


def test_validate_add_example_accepts_simple_text() -> None:
    check_can_apply(_DOC_WITH_BOTH, AddExampleAction("1.1", "fresh example"), None)


def test_validate_add_guidance_accepts_simple_text() -> None:
    check_can_apply(_DOC_WITH_BOTH, AddGuidanceAction("1.1", "fresh guidance"), None)


def test_validate_rejects_empty_text() -> None:
    check_can_apply(_DOC_WITH_BOTH, AddExampleAction("1.1", ""), SkipReason.InvalidContent)


def test_validate_rejects_whitespace_only_text() -> None:
    check_can_apply(_DOC_WITH_BOTH, AddGuidanceAction("1.1", "   \n\t  "), SkipReason.InvalidContent)


def test_validate_rejects_text_containing_fence_marker() -> None:
    check_can_apply(_DOC_WITH_BOTH, AddExampleAction("1.1", "foo ::: bar"), SkipReason.InvalidContent)


def test_validate_rejects_text_starting_with_heading() -> None:
    check_can_apply(_DOC_WITH_BOTH, AddExampleAction("1.1", "# heading"), SkipReason.InvalidContent)


def test_validate_rejects_text_starting_with_list_marker() -> None:
    check_can_apply(_DOC_WITH_BOTH, AddGuidanceAction("1.1", "- bullet"), SkipReason.InvalidContent)


def test_validate_rejects_text_starting_with_ordered_list_marker() -> None:
    check_can_apply(_DOC_WITH_BOTH, AddExampleAction("1.1", "1. first"), SkipReason.InvalidContent)


def test_validate_rejects_heading_on_continuation_line() -> None:
    check_can_apply(_DOC_WITH_BOTH, AddExampleAction("1.1", "intro\n## boom"), SkipReason.InvalidContent)


def test_validate_accepts_hash_mid_line() -> None:
    check_can_apply(_DOC_WITH_BOTH, AddExampleAction("1.1", "color #ff00aa"), None)


def test_validate_content_check_runs_before_host_lookup() -> None:
    # Bad text + missing host → reports the content problem first.
    check_can_apply(_DOC_WITH_BOTH, AddExampleAction("9.9.9", ""), SkipReason.InvalidContent)


# ---------- host resolution ----------


def test_validate_returns_target_not_found_for_unknown_host_id() -> None:
    check_can_apply(_DOC_WITH_BOTH, AddExampleAction("9.9.9", "x"), SkipReason.TargetNotFound)


def test_validate_guidance_returns_target_not_found_for_unknown_host_id() -> None:
    check_can_apply(_DOC_WITH_BOTH, AddGuidanceAction("9.9.9", "x"), SkipReason.TargetNotFound)


def test_validate_returns_host_not_annotatable_for_top_level_section_id() -> None:
    # `1` is the Section, not a Paragraph or ListItem.
    check_can_apply(_DOC_WITH_BOTH, AddExampleAction("1", "x"), SkipReason.HostNotAnnotatable)


def test_validate_returns_host_not_annotatable_for_nested_section_id() -> None:
    # `1.1` here is the nested Section, not a paragraph.
    check_can_apply(_DOC_NESTED, AddExampleAction("1.1", "x"), SkipReason.HostNotAnnotatable)


def test_validate_accepts_paragraph_host() -> None:
    check_can_apply(_DOC_WITH_BOTH, AddExampleAction("1.1", "x"), None)


def test_validate_accepts_list_item_host() -> None:
    check_can_apply(_DOC_LIST_HOST, AddExampleAction("1.1.1", "x"), None)


def test_validate_accepts_host_with_no_existing_group() -> None:
    # No existing examples group — add still validates; apply auto-creates.
    check_can_apply(_DOC_NO_ANNOTATIONS, AddExampleAction("1.1", "first ex"), None)


def test_validate_guidance_accepts_host_with_only_examples_group() -> None:
    md = "# Title\n\nBody paragraph.\n\n::: examples\nex\n:::\n"
    check_can_apply(md, AddGuidanceAction("1.1", "new g"), None)


def test_validate_rejects_empty_host_id() -> None:
    check_can_apply(_DOC_WITH_BOTH, AddExampleAction("", "x"), SkipReason.TargetNotFound)


# ---------- first_child / last_child anchors ----------


def test_validate_accepts_first_child_anchor_when_target_is_host() -> None:
    anchor = LocationAnchor(kind="first_child", target="1.1")
    check_can_apply(_DOC_WITH_BOTH, AddExampleAction("1.1", "x", anchor=anchor), None)


def test_validate_accepts_last_child_anchor_when_target_is_host() -> None:
    anchor = LocationAnchor(kind="last_child", target="1.1")
    check_can_apply(_DOC_WITH_BOTH, AddGuidanceAction("1.1", "x", anchor=anchor), None)


def test_validate_rejects_first_child_anchor_when_target_is_not_host() -> None:
    anchor = LocationAnchor(kind="first_child", target="1")
    check_can_apply(_DOC_WITH_BOTH, AddExampleAction("1.1", "x", anchor=anchor), SkipReason.InvalidAnchor)


def test_validate_rejects_last_child_anchor_when_target_is_annotation_id() -> None:
    anchor = LocationAnchor(kind="last_child", target="1.1.e1")
    check_can_apply(_DOC_WITH_BOTH, AddExampleAction("1.1", "x", anchor=anchor), SkipReason.InvalidAnchor)


def test_validate_accepts_first_child_with_no_existing_group() -> None:
    # Parent-relative anchors don't require an existing group on the host.
    anchor = LocationAnchor(kind="first_child", target="1.1")
    check_can_apply(_DOC_NO_ANNOTATIONS, AddExampleAction("1.1", "x", anchor=anchor), None)


# ---------- after / before anchors ----------


def test_validate_accepts_after_anchor_pointing_at_existing_example() -> None:
    anchor = LocationAnchor(kind="after", target="1.1.e1")
    check_can_apply(_DOC_WITH_MULTI, AddExampleAction("1.1", "x", anchor=anchor), None)


def test_validate_accepts_before_anchor_pointing_at_existing_example() -> None:
    anchor = LocationAnchor(kind="before", target="1.1.e2")
    check_can_apply(_DOC_WITH_MULTI, AddExampleAction("1.1", "x", anchor=anchor), None)


def test_validate_accepts_after_anchor_pointing_at_existing_guidance() -> None:
    anchor = LocationAnchor(kind="after", target="1.1.g1")
    check_can_apply(_DOC_WITH_MULTI, AddGuidanceAction("1.1", "x", anchor=anchor), None)


def test_validate_rejects_after_anchor_with_unknown_target() -> None:
    anchor = LocationAnchor(kind="after", target="1.1.e99")
    check_can_apply(_DOC_WITH_MULTI, AddExampleAction("1.1", "x", anchor=anchor), SkipReason.InvalidAnchor)


def test_validate_rejects_before_anchor_with_unknown_target() -> None:
    anchor = LocationAnchor(kind="before", target="1.1.g99")
    check_can_apply(_DOC_WITH_MULTI, AddGuidanceAction("1.1", "x", anchor=anchor), SkipReason.InvalidAnchor)


def test_validate_rejects_after_anchor_when_host_has_no_group_of_this_kind() -> None:
    md = "# Title\n\nBody paragraph.\n\n::: guidance\ng\n:::\n"
    anchor = LocationAnchor(kind="after", target="1.1.e1")
    check_can_apply(md, AddExampleAction("1.1", "x", anchor=anchor), SkipReason.InvalidAnchor)


def test_validate_rejects_example_after_anchor_pointing_at_guidance_id() -> None:
    # The id exists, but it lives in the guidance group — wrong kind for AddExample.
    anchor = LocationAnchor(kind="after", target="1.1.g1")
    check_can_apply(_DOC_WITH_MULTI, AddExampleAction("1.1", "x", anchor=anchor), SkipReason.InvalidAnchor)


def test_validate_rejects_guidance_before_anchor_pointing_at_example_id() -> None:
    anchor = LocationAnchor(kind="before", target="1.1.e1")
    check_can_apply(_DOC_WITH_MULTI, AddGuidanceAction("1.1", "x", anchor=anchor), SkipReason.InvalidAnchor)


def test_validate_rejects_after_anchor_pointing_at_another_hosts_annotation() -> None:
    md = "# Title\n\nFirst paragraph.\n\n::: examples\np1 e\n:::\n\nSecond paragraph.\n\n::: examples\np2 e\n:::\n"
    anchor = LocationAnchor(kind="after", target="1.2.e1")
    check_can_apply(md, AddExampleAction("1.1", "x", anchor=anchor), SkipReason.InvalidAnchor)


# ---------- purity ----------


def test_validate_does_not_mutate_tree() -> None:
    from prompt_model.service.parsing.parse_prompt import parse_from_string

    tree = parse_from_string(_DOC_WITH_BOTH)
    AddExampleAction("1.1", "new").validate(tree)
    AddExampleAction("9.9", "new").validate(tree)
    AddExampleAction("1.1", "x", anchor=LocationAnchor(kind="after", target="1.1.e99")).validate(tree)
    assert tree.to_markdown() == _DOC_WITH_BOTH


# ---------- apply(): anchor support — examples ----------

_DOC_3_EXAMPLES = "# Title\n\nBody paragraph.\n\n::: examples\n- e one\n- e two\n- e three\n:::\n"

_DOC_2_EXAMPLES = "# Title\n\nBody paragraph.\n\n::: examples\n- e one\n- e two\n:::\n"

_DOC_2_GUIDANCE = "# Title\n\nBody paragraph.\n\n::: guidance\n- g one\n- g two\n:::\n"

_DOC_3_GUIDANCE = "# Title\n\nBody paragraph.\n\n::: guidance\n- g one\n- g two\n- g three\n:::\n"


def test_apply_add_example_with_after_anchor_inserts_in_middle() -> None:
    expected = "# Title\n\nBody paragraph.\n\n::: examples\n- e one\n- e two\n- inserted\n- e three\n:::\n"
    anchor = LocationAnchor(kind="after", target="1.1.e2")
    check_against_md(_DOC_3_EXAMPLES, AddExampleAction("1.1", "inserted", anchor=anchor), expected)


def test_apply_add_example_with_before_anchor_at_start() -> None:
    expected = "# Title\n\nBody paragraph.\n\n::: examples\n- prepended\n- e one\n- e two\n:::\n"
    anchor = LocationAnchor(kind="before", target="1.1.e1")
    check_against_md(_DOC_2_EXAMPLES, AddExampleAction("1.1", "prepended", anchor=anchor), expected)


def test_apply_add_example_with_first_child_anchor_on_existing_group() -> None:
    expected = "# Title\n\nBody paragraph.\n\n::: examples\n- prepended\n- e one\n- e two\n:::\n"
    anchor = LocationAnchor(kind="first_child", target="1.1")
    check_against_md(_DOC_2_EXAMPLES, AddExampleAction("1.1", "prepended", anchor=anchor), expected)


def test_apply_add_example_with_last_child_anchor_matches_default_append() -> None:
    anchor = LocationAnchor(kind="last_child", target="1.1")
    expected = "# Title\n\nBody paragraph.\n\n::: examples\n- e one\n- e two\n- appended\n:::\n"
    check_against_md(_DOC_2_EXAMPLES, AddExampleAction("1.1", "appended", anchor=anchor), expected)
    # And the no-anchor form produces identical markdown.
    check_against_md(_DOC_2_EXAMPLES, AddExampleAction("1.1", "appended"), expected)


def test_undo_of_anchored_add_example_restores_original() -> None:
    anchor = LocationAnchor(kind="after", target="1.1.e1")
    check_undo(_DOC_3_EXAMPLES, [AddExampleAction("1.1", "inserted", anchor=anchor)])


def test_apply_add_example_with_first_child_anchor_on_host_with_no_group() -> None:
    # Auto-create the group with the single annotation, even when an anchor
    # is specified — the anchor path must not bypass group creation.
    expected = "# Title\n\nBody paragraph.\n\n::: examples\nonly\n:::\n"
    anchor = LocationAnchor(kind="first_child", target="1.1")
    check_against_md(_DOC_NO_ANNOTATIONS, AddExampleAction("1.1", "only", anchor=anchor), expected)


# ---------- apply(): anchor support — guidance ----------


def test_apply_add_guidance_with_after_anchor_inserts_in_middle() -> None:
    expected = "# Title\n\nBody paragraph.\n\n::: guidance\n- g one\n- g two\n- inserted\n- g three\n:::\n"
    anchor = LocationAnchor(kind="after", target="1.1.g2")
    check_against_md(_DOC_3_GUIDANCE, AddGuidanceAction("1.1", "inserted", anchor=anchor), expected)


def test_apply_add_guidance_with_before_anchor_at_start() -> None:
    expected = "# Title\n\nBody paragraph.\n\n::: guidance\n- prepended\n- g one\n- g two\n:::\n"
    anchor = LocationAnchor(kind="before", target="1.1.g1")
    check_against_md(_DOC_2_GUIDANCE, AddGuidanceAction("1.1", "prepended", anchor=anchor), expected)


def test_apply_add_guidance_with_first_child_anchor_on_existing_group() -> None:
    expected = "# Title\n\nBody paragraph.\n\n::: guidance\n- prepended\n- g one\n- g two\n:::\n"
    anchor = LocationAnchor(kind="first_child", target="1.1")
    check_against_md(_DOC_2_GUIDANCE, AddGuidanceAction("1.1", "prepended", anchor=anchor), expected)


def test_apply_add_guidance_with_last_child_anchor_matches_default_append() -> None:
    anchor = LocationAnchor(kind="last_child", target="1.1")
    expected = "# Title\n\nBody paragraph.\n\n::: guidance\n- g one\n- g two\n- appended\n:::\n"
    check_against_md(_DOC_2_GUIDANCE, AddGuidanceAction("1.1", "appended", anchor=anchor), expected)
    check_against_md(_DOC_2_GUIDANCE, AddGuidanceAction("1.1", "appended"), expected)


def test_undo_of_anchored_add_guidance_restores_original() -> None:
    anchor = LocationAnchor(kind="after", target="1.1.g1")
    check_undo(_DOC_3_GUIDANCE, [AddGuidanceAction("1.1", "inserted", anchor=anchor)])


def test_apply_add_guidance_with_first_child_anchor_on_host_with_no_group() -> None:
    expected = "# Title\n\nBody paragraph.\n\n::: guidance\nonly\n:::\n"
    anchor = LocationAnchor(kind="first_child", target="1.1")
    check_against_md(_DOC_NO_ANNOTATIONS, AddGuidanceAction("1.1", "only", anchor=anchor), expected)


# ---------- parse_action / _build (JSON entrypoint) ----------


def test_parse_action_builds_add_example_from_well_formed_dict() -> None:
    result = parse_action({"type": "add_example", "host_id": "1.1", "text": "hello"})
    assert isinstance(result, AddExampleAction)
    assert result.host_id == "1.1"
    assert result.text == "hello"
    assert result.anchor is None


def test_parse_action_builds_add_guidance_from_well_formed_dict() -> None:
    result = parse_action({"type": "add_guidance", "host_id": "1.1", "text": "hello"})
    assert isinstance(result, AddGuidanceAction)
    assert result.host_id == "1.1"
    assert result.text == "hello"
    assert result.anchor is None


def test_parse_action_builds_add_example_with_after_anchor() -> None:
    result = parse_action({"type": "add_example", "host_id": "1.1", "text": "x", "anchor": {"after": "1.1.e1"}})
    assert isinstance(result, AddExampleAction)
    assert result.anchor is not None
    assert result.anchor.kind == "after"
    assert result.anchor.target == "1.1.e1"


def test_parse_action_builds_add_guidance_with_first_child_anchor() -> None:
    result = parse_action({"type": "add_guidance", "host_id": "1.1", "text": "x", "anchor": {"first_child": "1.1"}})
    assert isinstance(result, AddGuidanceAction)
    assert result.anchor is not None
    assert result.anchor.kind == "first_child"
    assert result.anchor.target == "1.1"


def test_parse_action_returns_missing_required_when_host_id_absent() -> None:
    assert parse_action({"type": "add_example", "text": "x"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_host_id_empty() -> None:
    assert parse_action({"type": "add_example", "host_id": "", "text": "x"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_host_id_not_string() -> None:
    assert parse_action({"type": "add_example", "host_id": 42, "text": "x"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_text_absent() -> None:
    assert parse_action({"type": "add_example", "host_id": "1.1"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_text_empty() -> None:
    assert parse_action({"type": "add_example", "host_id": "1.1", "text": ""}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_text_whitespace_only() -> None:
    assert parse_action({"type": "add_example", "host_id": "1.1", "text": "  \n\t"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_text_not_string() -> None:
    assert parse_action({"type": "add_example", "host_id": "1.1", "text": 7}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_anchor_not_dict() -> None:
    assert parse_action({"type": "add_example", "host_id": "1.1", "text": "x", "anchor": "after"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_anchor_dict_has_no_known_key() -> None:
    assert parse_action({"type": "add_example", "host_id": "1.1", "text": "x", "anchor": {"sideways": "1.1"}}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_anchor_target_empty() -> None:
    assert parse_action({"type": "add_example", "host_id": "1.1", "text": "x", "anchor": {"after": ""}}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_anchor_target_not_string() -> None:
    assert parse_action({"type": "add_example", "host_id": "1.1", "text": "x", "anchor": {"after": 5}}) == SkipReason.MissingRequired


def test_parse_action_tolerates_extra_unknown_keys() -> None:
    result = parse_action({"type": "add_example", "host_id": "1.1", "text": "x", "comment": "ignored", "rank": 3})
    assert isinstance(result, AddExampleAction)
    assert result.host_id == "1.1"


def test_parse_action_returns_unknown_type_for_unregistered_type() -> None:
    assert parse_action({"type": "add_nothing", "host_id": "1.1", "text": "x"}) == SkipReason.UnknownType


# ---------- inverse action behavior (direct) ----------


def test_apply_returns_inverse_that_removes_only_the_added_example() -> None:
    tree = parse_from_string(_DOC_2_EXAMPLES)
    inverse = AddExampleAction("1.1", "added", anchor=LocationAnchor(kind="after", target="1.1.e1")).apply(tree)
    # tree currently has 3 example children
    section = tree.children[0]
    assert isinstance(section, Section)
    para = section.children[0]
    assert isinstance(para, Paragraph)
    assert para.examples is not None
    assert [c.text for c in para.examples.children] == ["e one", "added", "e two"]
    # Apply the inverse — only the added one is gone, originals intact in order.
    inverse.apply(tree)
    assert [c.text for c in para.examples.children] == ["e one", "e two"]


def test_inverse_tears_down_group_when_added_annotation_was_the_only_one() -> None:
    tree = parse_from_string(_DOC_NO_ANNOTATIONS)
    inverse = AddExampleAction("1.1", "only").apply(tree)
    section = tree.children[0]
    assert isinstance(section, Section)
    para = section.children[0]
    assert isinstance(para, Paragraph)
    assert para.examples is not None  # group auto-created
    inverse.apply(tree)
    # Host's `examples` attribute must be None — not just an empty group.
    assert para.examples is None


def test_inverse_tears_down_guidance_group_when_only_child_removed() -> None:
    tree = parse_from_string(_DOC_NO_ANNOTATIONS)
    inverse = AddGuidanceAction("1.1", "only").apply(tree)
    section = tree.children[0]
    assert isinstance(section, Section)
    para = section.children[0]
    assert isinstance(para, Paragraph)
    assert para.guidance is not None
    inverse.apply(tree)
    assert para.guidance is None


def test_inverse_apply_returns_a_callable_action() -> None:
    # The inverse's apply() must itself return an Action (a redo) — required
    # by the protocol contract even though tests don't normally exercise it.
    tree = parse_from_string(_DOC_NO_ANNOTATIONS)
    inverse = AddExampleAction("1.1", "only").apply(tree)
    redo = inverse.apply(tree)
    assert not isinstance(redo, list)
    redo_action: Action = redo
    # Redoing puts the annotation back.
    section = tree.children[0]
    assert isinstance(section, Section)
    para = section.children[0]
    assert isinstance(para, Paragraph)
    assert para.examples is None
    redo_action.apply(tree)
    assert para.examples is not None
    assert [c.text for c in para.examples.children] == ["only"]


def test_inverse_with_siblings_does_not_touch_group_attribute() -> None:
    # Adding into a group with existing entries, then undoing, must leave the
    # group object intact (not replaced) and other annotations untouched.
    tree = parse_from_string(_DOC_2_EXAMPLES)
    section = tree.children[0]
    assert isinstance(section, Section)
    para = section.children[0]
    assert isinstance(para, Paragraph)
    original_group = para.examples
    assert original_group is not None
    inverse = AddExampleAction("1.1", "x").apply(tree)
    inverse.apply(tree)
    assert para.examples is original_group
    assert [c.text for c in original_group.children] == ["e one", "e two"]


# ---------- multi-action undo ----------


def test_multi_add_undo_restores_tree() -> None:
    actions: list[Action] = [
        AddExampleAction("1.1", "ex a"),
        AddExampleAction("1.1", "ex b", anchor=LocationAnchor(kind="first_child", target="1.1")),
        AddGuidanceAction("1.1", "g a"),
        AddExampleAction("1.1", "ex c", anchor=LocationAnchor(kind="after", target="1.1.e1")),
    ]
    check_undo(_DOC_NO_ANNOTATIONS, actions)


def test_interleaved_add_remove_groups_undo_restores_tree() -> None:
    # Start from a doc with both groups already populated; pile on more adds
    # of both kinds, then unwind. Catches inverses that resolve siblings by
    # ID after the tree has shifted underneath them.
    actions: list[Action] = [
        AddExampleAction("1.1", "ex2", anchor=LocationAnchor(kind="before", target="1.1.e1")),
        AddGuidanceAction("1.1", "g2", anchor=LocationAnchor(kind="last_child", target="1.1")),
        AddExampleAction("1.1", "ex3"),
        AddGuidanceAction("1.1", "g3", anchor=LocationAnchor(kind="first_child", target="1.1")),
    ]
    check_undo(_DOC_WITH_BOTH, actions)


# ---------- ListItem hosts with anchors ----------


def test_apply_add_example_with_after_anchor_on_list_item_host() -> None:
    input_md = "# Title\n\n- item one\n\n  ::: examples\n  - on item 1\n  - on item 2\n  :::\n"
    expected = "# Title\n\n- item one\n  ::: examples\n  - on item 1\n  - new\n  - on item 2\n  :::\n"
    anchor = LocationAnchor(kind="after", target="1.1.1.e1")
    check_against_md(input_md, AddExampleAction("1.1.1", "new", anchor=anchor), expected)


def test_apply_add_guidance_with_first_child_anchor_on_list_item_host() -> None:
    input_md = "# Title\n\n- item one\n\n  ::: guidance\n  - g1\n  - g2\n  :::\n"
    expected = "# Title\n\n- item one\n  ::: guidance\n  - new\n  - g1\n  - g2\n  :::\n"
    anchor = LocationAnchor(kind="first_child", target="1.1.1")
    check_against_md(input_md, AddGuidanceAction("1.1.1", "new", anchor=anchor), expected)


def test_apply_add_example_on_nested_list_item_host() -> None:
    # Shorthand `h1 ul1 ul2 e` puts an annotation at id `1.1.1.1.1.e1`; the
    # inner list item id is `1.1.1.1.1`. The walk must descend into the
    # nested list to find the host before adding the new annotation.
    tree = doc_from_shorthand("h1 ul1 ul2 e")
    anchor = LocationAnchor(kind="after", target="1.1.1.1.1.e1")
    AddExampleAction("1.1.1.1.1", "deep new", anchor=anchor).apply(tree)
    # Walk to the inner item and confirm the new annotation landed correctly.
    section = tree.children[0]
    assert isinstance(section, Section)
    from prompt_model.model import List, ListItem

    outer_list = section.children[0]
    assert isinstance(outer_list, List)
    outer_item = outer_list.children[0]
    assert isinstance(outer_item, ListItem)
    inner_list = outer_item.children[0]
    assert isinstance(inner_list, List)
    inner_item = inner_list.children[0]
    assert isinstance(inner_item, ListItem)
    assert inner_item.examples is not None
    assert len(inner_item.examples.children) == 2
    assert inner_item.examples.children[1].text == "deep new"


# ---------- text-form ⇄ list-form rendering transition ----------


def test_apply_promotes_single_child_group_to_list_form() -> None:
    # The group renders text-form for one child, list-form for >1. Adding a
    # second annotation must flip the rendering.
    input_md = "# Title\n\nBody paragraph.\n\n::: examples\nsolo\n:::\n"
    expected = "# Title\n\nBody paragraph.\n\n::: examples\n- solo\n- added\n:::\n"
    check_against_md(input_md, AddExampleAction("1.1", "added"), expected)


def test_undo_demotes_two_child_group_back_to_text_form() -> None:
    # Add a second child (promotes to list-form), then undo back to one child
    # (must demote back to text-form). Captured via byte-equal round-trip.
    input_md = "# Title\n\nBody paragraph.\n\n::: examples\nsolo\n:::\n"
    check_undo(input_md, [AddExampleAction("1.1", "added")])


def test_apply_promotes_single_child_guidance_group_to_list_form() -> None:
    input_md = "# Title\n\nBody paragraph.\n\n::: guidance\nsolo\n:::\n"
    expected = "# Title\n\nBody paragraph.\n\n::: guidance\n- solo\n- added\n:::\n"
    check_against_md(input_md, AddGuidanceAction("1.1", "added"), expected)


# ---------- multi-line text round-trips ----------


def test_apply_add_example_with_paragraph_break_text() -> None:
    # Empty host → group becomes text-form with a single multi-paragraph
    # annotation. The blank-line separator inside the annotation body
    # must round-trip through the renderer.
    input_md = "# Title\n\nBody paragraph.\n"
    expected = "# Title\n\nBody paragraph.\n\n::: examples\nfoo foo foo\n\nbird bird bird\n:::\n"
    check_against_md(input_md, AddExampleAction("1.1", "foo foo foo\n\nbird bird bird"), expected)


def test_apply_add_example_multiline_into_list_form_group() -> None:
    # Existing list-form group → continuation lines of the new annotation get
    # 2-space indent under the `- ` marker, with a blank line before the
    # paragraph break (same rendering as the update test of the same shape).
    input_md = "# Title\n\nBody paragraph.\n\n::: examples\n- a\n- b\n:::\n"
    expected = "# Title\n\nBody paragraph.\n\n::: examples\n- a\n- b\n- foo foo foo\n\n  bird bird bird\n:::\n"
    check_against_md(input_md, AddExampleAction("1.1", "foo foo foo\n\nbird bird bird"), expected)


def test_undo_of_multiline_add_round_trips() -> None:
    input_md = "# Title\n\nBody paragraph.\n\n::: examples\n- a\n- b\n:::\n"
    check_undo(input_md, [AddExampleAction("1.1", "line one\n\nline two")])


# ---------- targeting across multiple hosts ----------


def test_add_targets_correct_host_when_multiple_paragraphs_have_examples() -> None:
    input_md = (
        "# Title\n\nFirst paragraph.\n\n::: examples\n- p1 e1\n- p1 e2\n:::\n\nSecond paragraph.\n\n::: examples\n- p2 e1\n- p2 e2\n:::\n"
    )
    expected = (
        "# Title\n\nFirst paragraph.\n\n::: examples\n- p1 e1\n- p1 e2\n:::\n\n"
        "Second paragraph.\n\n::: examples\n- p2 e1\n- p2 e2\n- added\n:::\n"
    )
    check_against_md(input_md, AddExampleAction("1.2", "added"), expected)


def test_add_does_not_create_group_on_wrong_host() -> None:
    # The first paragraph has neither group; the second has examples. Adding
    # guidance to the first host must touch only the first host.
    input_md = "# Title\n\nFirst paragraph.\n\nSecond paragraph.\n\n::: examples\nkeep\n:::\n"
    expected = "# Title\n\nFirst paragraph.\n\n::: guidance\nnew g\n:::\n\nSecond paragraph.\n\n::: examples\nkeep\n:::\n"
    check_against_md(input_md, AddGuidanceAction("1.1", "new g"), expected)


def test_add_undo() -> None:
    sh = "h1 p"
    actions: list[Action] = [
        AddExampleAction("1.1", "aaa", LocationAnchor(kind="first_child", target="1.1")),
        AddExampleAction("1.1", "bbb", LocationAnchor(kind="after", target="1.1.e1")),
        AddExampleAction("1.1", "ccc", LocationAnchor(kind="before", target="1.1.e1")),
        AddExampleAction("1.1", "ddd", LocationAnchor(kind="after", target="1.1.e1")),
        AddExampleAction("1.1", "eee", LocationAnchor(kind="before", target="1.1.e3")),
        AddExampleAction("1.1", "fff", LocationAnchor(kind="after", target="1.1.e2")),
        AddExampleAction("1.1", "ggg", LocationAnchor(kind="first_child", target="1.1")),
        AddExampleAction("1.1", "hhh", LocationAnchor(kind="last_child", target="1.1")),
    ]
    check_undo_from_sh(shorthand=sh, actions=actions)
