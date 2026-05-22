from __future__ import annotations

from prompt_model._actions import (
    SkipReason,
    UpdateExampleAction,
    UpdateGuidanceAction,
    parse_action,
)
from prompt_model._prompt import List, ListItem, Section
from prompt_model._prompt.parsing.parse_prompt import parse_from_string

from ..utils._short_hand import doc_from_shorthand
from ..utils.actions import check_against_md, check_can_apply

# ---------- update_example ----------


def test_update_example_replaces_paragraph_example_text() -> None:
    input_md = "# Title\n\nBody paragraph.\n\n::: examples\nold example\n:::\n"
    expected_md = "# Title\n\nBody paragraph.\n\n::: examples\nnew example\n:::\n"
    action = UpdateExampleAction("1.1.e1", "new example")
    check_against_md(input_md, action, expected_md)


def test_update_example_replaces_listitem_example_text() -> None:
    input_md = "# Title\n\n- item one\n\n  ::: examples\n  old example\n  :::\n"
    expected_md = "# Title\n\n- item one\n  ::: examples\n  fresh example\n  :::\n"
    action = UpdateExampleAction("1.1.1.e1", "fresh example")
    check_against_md(input_md, action, expected_md)


def test_update_example_leaves_sibling_guidance_untouched() -> None:
    input_md = "# Title\n\nBody paragraph.\n\n::: examples\nold example\n:::\n\n::: guidance\nkeep me\n:::\n"
    expected_md = "# Title\n\nBody paragraph.\n\n::: examples\nreplaced\n:::\n\n::: guidance\nkeep me\n:::\n"
    action = UpdateExampleAction("1.1.e1", "replaced")
    check_against_md(input_md, action, expected_md)


def test_update_example_replaces_one_annotation_in_list_form_group() -> None:
    # The host has three list-form examples (e1, e2, e3). Updating e1
    # changes only its text; e2 and e3 are untouched. Multi-line replacement
    # text indents continuation lines under the `-` marker.
    input_md = "# test\n\nbla blah blah\n\n::: examples\n- first example\n- second example\n- third example\n:::\n"
    expected_md = "# test\n\nbla blah blah\n\n::: examples\n- first example\n- test test test\n- third example\n:::\n"
    new_text = "test test test"
    action = UpdateExampleAction("1.1.e2", new_text)
    check_against_md(input_md, action, expected_md)


# ---------- update_guidance ----------


def test_update_guidance_replaces_paragraph_guidance_text() -> None:
    input_md = "# Title\n\nBody paragraph.\n\n::: guidance\nold guidance\n:::\n"
    expected_md = "# Title\n\nBody paragraph.\n\n::: guidance\nnew guidance\n:::\n"
    action = UpdateGuidanceAction("1.1.g1", "new guidance")
    check_against_md(input_md, action, expected_md)


def test_update_guidance_replaces_listitem_guidance_text() -> None:
    input_md = "# Title\n\n- item one\n\n  ::: guidance\n  old guidance\n  :::\n"
    expected_md = "# Title\n\n- item one\n  ::: guidance\n  fresh guidance\n  :::\n"
    action = UpdateGuidanceAction("1.1.1.g1", "fresh guidance")
    check_against_md(input_md, action, expected_md)


def test_update_guidance_leaves_sibling_example_untouched() -> None:
    input_md = "# Title\n\nBody paragraph.\n\n::: examples\nkeep me\n:::\n\n::: guidance\nold guidance\n:::\n"
    expected_md = "# Title\n\nBody paragraph.\n\n::: examples\nkeep me\n:::\n\n::: guidance\nreplaced\n:::\n"
    action = UpdateGuidanceAction("1.1.g1", "replaced")
    check_against_md(input_md, action, expected_md)


def test_multi_line_example_update() -> None:
    input_md: str = """# foo
test test test

::: examples
blah blah blah blah.
foo foo foo.

bar bar bar.
:::

- aa
"""
    expected_md: str = """# foo

test test test

::: examples
a small dog
:::

- aa
"""
    action = UpdateExampleAction("1.1.e1", "a small dog")
    check_against_md(input_md, action, expected_md)


def test_update_with_multiline() -> None:
    input_md: str = """# foo
test test test

::: examples
test test test
:::

- aa
"""
    expected_md: str = """# foo

test test test

::: examples
foo foo foo

bird bird bird
:::

- aa
"""
    action = UpdateExampleAction("1.1.e1", "foo foo foo\n\nbird bird bird")
    check_against_md(input_md, action, expected_md)


def test_update_list_with_multiline() -> None:
    input_md: str = """# foo
test test test

::: examples
- aa
- bb
- cc
:::

- aa
"""
    expected_md: str = """# foo

test test test

::: examples
- foo foo foo

  bird bird bird
- bb
- cc
:::

- aa
"""
    action = UpdateExampleAction("1.1.e1", "foo foo foo\n\nbird bird bird")
    check_against_md(input_md, action, expected_md)


# ---------- validate() ----------

_DOC_WITH_BOTH = "# Title\n\nBody paragraph.\n\n::: examples\nex one\n:::\n\n::: guidance\ng one\n:::\n"


def test_validate_example_success_when_id_resolves() -> None:
    check_can_apply(_DOC_WITH_BOTH, UpdateExampleAction("1.1.e1", "new"), None)


def test_validate_guidance_success_when_id_resolves() -> None:
    check_can_apply(_DOC_WITH_BOTH, UpdateGuidanceAction("1.1.g1", "new"), None)


def test_validate_example_returns_not_found_when_id_absent() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e99", "new"),
        SkipReason.AnnotationNotFound,
    )


def test_validate_guidance_returns_not_found_when_id_absent() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateGuidanceAction("1.1.g99", "new"),
        SkipReason.AnnotationNotFound,
    )


def test_validate_example_rejects_guidance_id() -> None:
    # `1.1.g1` is a real annotation, but it lives in the guidance group, so
    # an UpdateExampleAction targeting it must not resolve.
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.g1", "new"),
        SkipReason.AnnotationNotFound,
    )


def test_validate_guidance_rejects_example_id() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateGuidanceAction("1.1.e1", "new"),
        SkipReason.AnnotationNotFound,
    )


def test_validate_rejects_id_pointing_to_non_annotation_node() -> None:
    # `1.1` is the paragraph host, not an annotation.
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1", "new"),
        SkipReason.AnnotationNotFound,
    )


def test_validate_rejects_malformed_id() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("not-an-id", "new"),
        SkipReason.AnnotationNotFound,
    )


def test_validate_rejects_empty_id() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("", "new"),
        SkipReason.AnnotationNotFound,
    )


def test_validate_on_document_with_no_annotations_returns_not_found() -> None:
    md = "# Title\n\nJust a paragraph, no annotations.\n"
    check_can_apply(
        md,
        UpdateExampleAction("1.1.e1", "new"),
        SkipReason.AnnotationNotFound,
    )


def test_validate_locates_listitem_annotation() -> None:
    # Annotations attached to a ListItem (id form `1.1.1.e1`) must be found
    # by the walk, not just paragraph-hosted ones.
    md = "# Title\n\n- item one\n\n  ::: examples\n  ex on item\n  :::\n"
    check_can_apply(md, UpdateExampleAction("1.1.1.e1", "new"), None)


def test_validate_rejects_empty_text() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", ""),
        SkipReason.InvalidContent,
    )


def test_validate_rejects_whitespace_only_text() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "   \n\t  "),
        SkipReason.InvalidContent,
    )


def test_validate_guidance_rejects_empty_text() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateGuidanceAction("1.1.g1", ""),
        SkipReason.InvalidContent,
    )


def test_validate_rejects_text_equal_to_fence_marker() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", ":::"),
        SkipReason.InvalidContent,
    )


def test_validate_rejects_text_containing_fence_marker_mid_string() -> None:
    # Anywhere in the text is rejected — a line-internal `:::` would still
    # produce a `:::`-prefixed line under list-form continuation indenting,
    # which could close the host fence.
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "foo ::: bar"),
        SkipReason.InvalidContent,
    )


def test_validate_rejects_text_with_fence_marker_on_continuation_line() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "ok line one\n:::\nok line three"),
        SkipReason.InvalidContent,
    )


def test_validate_rejects_text_starting_with_heading() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "# heading"),
        SkipReason.InvalidContent,
    )


def test_validate_rejects_text_starting_with_h6() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "###### deep heading"),
        SkipReason.InvalidContent,
    )


def test_validate_rejects_heading_on_continuation_line() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "ok start\n## boom\nrest"),
        SkipReason.InvalidContent,
    )


def test_validate_rejects_indented_heading_line() -> None:
    # ATX heading still parses with up to 3 spaces of indent; we reject any
    # leading-whitespace + '#' pattern to match what the markdown parser does.
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "intro\n   # heading\nrest"),
        SkipReason.InvalidContent,
    )


def test_validate_rejects_text_starting_with_list_marker() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "- bullet"),
        SkipReason.InvalidContent,
    )


def test_validate_rejects_list_marker_on_continuation_line() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "intro paragraph\n- bullet"),
        SkipReason.InvalidContent,
    )


def test_validate_accepts_hash_mid_line() -> None:
    # `#` not at the start of a line is fine — it's not a heading marker.
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "color is #ff00aa in this design"),
        None,
    )


def test_validate_accepts_dash_mid_line() -> None:
    # Hyphenated words / em-dash style are not list markers.
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "this is a well-formed sentence"),
        None,
    )


def test_validate_accepts_hash_without_space() -> None:
    # `#foo` (no space after the hash) is not an ATX heading in CommonMark.
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "#foo is a tag, not a heading"),
        None,
    )


def test_validate_content_check_runs_before_id_lookup() -> None:
    # An action with bad content AND a bad id reports the content problem;
    # content validity is a property of the action and is cheaper to check.
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e99", ""),
        SkipReason.InvalidContent,
    )


def test_validate_does_not_mutate_tree() -> None:
    # validate() is a pure lookup. Calling it (success or failure) must leave
    # the annotation text untouched.

    tree = parse_from_string(_DOC_WITH_BOTH)
    UpdateExampleAction("1.1.e1", "replacement").validate(tree)
    UpdateExampleAction("1.1.e99", "replacement").validate(tree)
    assert tree.to_markdown() == _DOC_WITH_BOTH


# ---------- rejected list / heading markers (regression: ordered + alt bullets) ----------


def test_validate_rejects_text_starting_with_ordered_list_marker() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "1. first"),
        SkipReason.InvalidContent,
    )


def test_validate_rejects_ordered_marker_on_continuation_line() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "intro line\n1. boom"),
        SkipReason.InvalidContent,
    )


def test_validate_rejects_text_starting_with_asterisk_bullet() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "* bullet"),
        SkipReason.InvalidContent,
    )


def test_validate_rejects_text_starting_with_plus_bullet() -> None:
    check_can_apply(
        _DOC_WITH_BOTH,
        UpdateExampleAction("1.1.e1", "+ bullet"),
        SkipReason.InvalidContent,
    )


# ---------- _build / parse_action (JSON entrypoint used by the actor LLM) ----------


def test_parse_action_builds_update_example_from_well_formed_dict() -> None:
    result = parse_action({"type": "update_example", "id": "1.1.e1", "text": "hello"})
    assert isinstance(result, UpdateExampleAction)
    assert result.annotation_id == "1.1.e1"
    assert result.text == "hello"


def test_parse_action_builds_update_guidance_from_well_formed_dict() -> None:
    result = parse_action({"type": "update_guidance", "id": "1.1.g1", "text": "hello"})
    assert isinstance(result, UpdateGuidanceAction)
    assert result.annotation_id == "1.1.g1"
    assert result.text == "hello"


def test_parse_action_returns_unknown_type_for_unregistered_type() -> None:
    assert parse_action({"type": "does_not_exist", "id": "1.1.e1", "text": "x"}) == SkipReason.UnknownType


def test_parse_action_returns_missing_required_when_type_absent() -> None:
    assert parse_action({"id": "1.1.e1", "text": "x"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_type_not_string() -> None:
    assert parse_action({"type": 7, "id": "1.1.e1", "text": "x"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_id_absent() -> None:
    assert parse_action({"type": "update_example", "text": "x"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_id_empty() -> None:
    assert parse_action({"type": "update_example", "id": "", "text": "x"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_id_not_string() -> None:
    assert parse_action({"type": "update_example", "id": 42, "text": "x"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_text_absent() -> None:
    assert parse_action({"type": "update_example", "id": "1.1.e1"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_text_empty() -> None:
    assert parse_action({"type": "update_example", "id": "1.1.e1", "text": ""}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_text_whitespace_only() -> None:
    assert parse_action({"type": "update_example", "id": "1.1.e1", "text": "  \n\t"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_text_not_string() -> None:
    assert parse_action({"type": "update_example", "id": "1.1.e1", "text": 7}) == SkipReason.MissingRequired


def test_parse_action_tolerates_extra_unknown_keys() -> None:
    result = parse_action({"type": "update_example", "id": "1.1.e1", "text": "hi", "comment": "ignored", "rank": 3})
    assert isinstance(result, UpdateExampleAction)
    assert result.annotation_id == "1.1.e1"
    assert result.text == "hi"


# ---------- targeting across multiple hosts ----------


def test_update_targets_correct_host_when_multiple_paragraphs_have_examples() -> None:
    # Two paragraphs each with two example annotations. Updating 1.2.e1 must
    # change *only* that annotation; the other three must be untouched.
    input_md = (
        "# Title\n\nFirst paragraph.\n\n::: examples\n- p1 e1\n- p1 e2\n:::\n\nSecond paragraph.\n\n::: examples\n- p2 e1\n- p2 e2\n:::\n"
    )
    expected_md = (
        "# Title\n\n"
        "First paragraph.\n\n"
        "::: examples\n- p1 e1\n- p1 e2\n:::\n\n"
        "Second paragraph.\n\n"
        "::: examples\n- replaced\n- p2 e2\n:::\n"
    )
    check_against_md(input_md, UpdateExampleAction("1.2.e1", "replaced"), expected_md)


# ---------- nested list item annotation ----------


def test_validate_locates_annotation_on_nested_list_item() -> None:
    # Shorthand `h1 ul1 ul2 e` builds:
    #   section 1
    #     list 1.1
    #       item 1.1.1
    #         list 1.1.1.1
    #           item 1.1.1.1.1
    #             example annotation 1.1.1.1.1.e1
    # The walk must descend into the nested list to find the annotation.
    tree = doc_from_shorthand("h1 ul1 ul2 e")
    assert UpdateExampleAction("1.1.1.1.1.e1", "new").validate(tree) is None


def test_apply_updates_annotation_on_nested_list_item() -> None:
    tree = doc_from_shorthand("h1 ul1 ul2 e")
    UpdateExampleAction("1.1.1.1.1.e1", "new text").apply(tree)
    # Walk to the deeply-nested annotation and confirm only its text changed.
    section = tree.children[0]
    assert isinstance(section, Section)
    outer_list = section.children[0]
    assert isinstance(outer_list, List)
    outer_item = outer_list.children[0]
    assert isinstance(outer_item, ListItem)
    inner_list = outer_item.children[0]
    assert isinstance(inner_list, List)
    inner_item = inner_list.children[0]
    assert isinstance(inner_item, ListItem)
    assert inner_item.examples is not None
    assert inner_item.examples.children[0].text == "new text"
