from __future__ import annotations

from prompt_model.actions import (
    RemoveExampleAction,
    RemoveGuidanceAction,
    SkipReason,
    parse_action,
)
from prompt_model.prompt import List, ListItem, Section
from prompt_model.prompt.parsing.parse_prompt import parse_from_string

from ..utils._short_hand import doc_from_shorthand
from ..utils.actions import check_against_md, check_can_apply

# ---------- single-child removal tears down the group ----------


def test_remove_example_clears_group_when_only_child() -> None:
    input_md = "# Title\n\nBody paragraph.\n\n::: examples\nthe only one\n:::\n"
    expected_md = "# Title\n\nBody paragraph.\n"
    check_against_md(input_md, RemoveExampleAction("1.1.e1"), expected_md)


def test_remove_guidance_clears_group_when_only_child() -> None:
    input_md = "# Title\n\nBody paragraph.\n\n::: guidance\nonly one\n:::\n"
    expected_md = "# Title\n\nBody paragraph.\n"
    check_against_md(input_md, RemoveGuidanceAction("1.1.g1"), expected_md)


def test_remove_example_leaves_sibling_guidance_untouched() -> None:
    input_md = "# Title\n\nBody paragraph.\n\n::: examples\nex one\n:::\n\n::: guidance\nkeep me\n:::\n"
    expected_md = "# Title\n\nBody paragraph.\n\n::: guidance\nkeep me\n:::\n"
    check_against_md(input_md, RemoveExampleAction("1.1.e1"), expected_md)


def test_remove_guidance_leaves_sibling_examples_untouched() -> None:
    input_md = "# Title\n\nBody paragraph.\n\n::: examples\nkeep me\n:::\n\n::: guidance\ng one\n:::\n"
    expected_md = "# Title\n\nBody paragraph.\n\n::: examples\nkeep me\n:::\n"
    check_against_md(input_md, RemoveGuidanceAction("1.1.g1"), expected_md)


# ---------- list-form group: removing one of many ----------


def test_remove_example_from_list_form_group_demotes_to_text_form() -> None:
    # Two children → list-form. Removing one leaves a single child, which
    # must render in text form (no `-` marker).
    input_md = "# Title\n\nBody paragraph.\n\n::: examples\n- keep\n- drop\n:::\n"
    expected_md = "# Title\n\nBody paragraph.\n\n::: examples\nkeep\n:::\n"
    check_against_md(input_md, RemoveExampleAction("1.1.e2"), expected_md)


def test_remove_middle_of_three_examples_preserves_order() -> None:
    input_md = "# Title\n\nBody paragraph.\n\n::: examples\n- first\n- middle\n- last\n:::\n"
    expected_md = "# Title\n\nBody paragraph.\n\n::: examples\n- first\n- last\n:::\n"
    check_against_md(input_md, RemoveExampleAction("1.1.e2"), expected_md)


def test_remove_first_of_three_guidances_preserves_order() -> None:
    input_md = "# Title\n\nBody paragraph.\n\n::: guidance\n- first\n- middle\n- last\n:::\n"
    expected_md = "# Title\n\nBody paragraph.\n\n::: guidance\n- middle\n- last\n:::\n"
    check_against_md(input_md, RemoveGuidanceAction("1.1.g1"), expected_md)


# ---------- list-item hosts ----------


def test_remove_example_on_list_item_host() -> None:
    input_md = "# Title\n\n- item one\n\n  ::: examples\n  the only one\n  :::\n"
    expected_md = "# Title\n\n- item one\n"
    check_against_md(input_md, RemoveExampleAction("1.1.1.e1"), expected_md)


def test_remove_example_on_nested_list_item_host() -> None:
    # Shorthand `h1 ul1 ul2 e` produces an annotation at 1.1.1.1.1.e1
    # on a deeply-nested list item; the walk must descend into it.
    tree = doc_from_shorthand("h1 ul1 ul2 e")
    assert RemoveExampleAction("1.1.1.1.1.e1").validate(tree) is None
    RemoveExampleAction("1.1.1.1.1.e1").apply(tree)
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
    assert inner_item.examples is None


# ---------- validate() ----------

_DOC_WITH_BOTH = "# Title\n\nBody paragraph.\n\n::: examples\nex one\n:::\n\n::: guidance\ng one\n:::\n"


def test_validate_success_when_id_resolves() -> None:
    check_can_apply(_DOC_WITH_BOTH, RemoveExampleAction("1.1.e1"), None)
    check_can_apply(_DOC_WITH_BOTH, RemoveGuidanceAction("1.1.g1"), None)


def test_validate_returns_not_found_for_missing_id() -> None:
    check_can_apply(_DOC_WITH_BOTH, RemoveExampleAction("1.1.e99"), SkipReason.AnnotationNotFound)
    check_can_apply(_DOC_WITH_BOTH, RemoveGuidanceAction("1.1.g99"), SkipReason.AnnotationNotFound)


def test_validate_rejects_cross_kind_id() -> None:
    # The id resolves in the document, but it points at the *other* kind of
    # group — RemoveExample must not delete a guidance annotation.
    check_can_apply(_DOC_WITH_BOTH, RemoveExampleAction("1.1.g1"), SkipReason.AnnotationNotFound)
    check_can_apply(_DOC_WITH_BOTH, RemoveGuidanceAction("1.1.e1"), SkipReason.AnnotationNotFound)


def test_validate_rejects_id_pointing_to_non_annotation_node() -> None:
    check_can_apply(_DOC_WITH_BOTH, RemoveExampleAction("1.1"), SkipReason.AnnotationNotFound)


def test_validate_rejects_empty_id() -> None:
    check_can_apply(_DOC_WITH_BOTH, RemoveExampleAction(""), SkipReason.AnnotationNotFound)


def test_validate_does_not_mutate_tree() -> None:
    tree = parse_from_string(_DOC_WITH_BOTH)
    RemoveExampleAction("1.1.e1").validate(tree)
    RemoveExampleAction("1.1.e99").validate(tree)
    assert tree.to_markdown() == _DOC_WITH_BOTH


# ---------- multi-host targeting ----------


def test_remove_targets_correct_host_when_multiple_paragraphs_have_examples() -> None:
    input_md = (
        "# Title\n\nFirst paragraph.\n\n::: examples\n- p1 e1\n- p1 e2\n:::\n\nSecond paragraph.\n\n::: examples\n- p2 e1\n- p2 e2\n:::\n"
    )
    expected = "# Title\n\nFirst paragraph.\n\n::: examples\n- p1 e1\n- p1 e2\n:::\n\nSecond paragraph.\n\n::: examples\np2 e2\n:::\n"
    check_against_md(input_md, RemoveExampleAction("1.2.e1"), expected)


# ---------- parse_action / _build (JSON entrypoint) ----------


def test_parse_action_builds_remove_example() -> None:
    result = parse_action({"type": "remove_example", "id": "1.1.e1"})
    assert isinstance(result, RemoveExampleAction)
    assert result.annotation_id == "1.1.e1"


def test_parse_action_builds_remove_guidance() -> None:
    result = parse_action({"type": "remove_guidance", "id": "1.1.g1"})
    assert isinstance(result, RemoveGuidanceAction)
    assert result.annotation_id == "1.1.g1"


def test_parse_action_returns_missing_required_when_id_absent() -> None:
    assert parse_action({"type": "remove_example"}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_id_empty() -> None:
    assert parse_action({"type": "remove_example", "id": ""}) == SkipReason.MissingRequired


def test_parse_action_returns_missing_required_when_id_not_string() -> None:
    assert parse_action({"type": "remove_example", "id": 42}) == SkipReason.MissingRequired


def test_parse_action_tolerates_extra_unknown_keys() -> None:
    result = parse_action({"type": "remove_guidance", "id": "1.1.g1", "comment": "ignored"})
    assert isinstance(result, RemoveGuidanceAction)
    assert result.annotation_id == "1.1.g1"


def test_examples_simple_3() -> None:
    three_items_md = """# foo

test test test

::: examples
- first
- second
- third
:::
"""

    two_items_md = """# foo

test test test

::: examples
- second
- third
:::
"""

    one_item_md = """# foo

test test test

::: examples
third
:::
"""

    no_items_md = """# foo

test test test
"""

    action: RemoveExampleAction = RemoveExampleAction("1.1.e1")
    check_against_md(three_items_md, action, two_items_md)
    check_against_md(two_items_md, action, one_item_md)
    check_against_md(one_item_md, action, no_items_md)


def test_guidance_simple_3() -> None:
    three_items_md = """# foo

test test test

::: guidance
- first
- second
- third
:::
"""

    two_items_md = """# foo

test test test

::: guidance
- second
- third
:::
"""

    one_item_md = """# foo

test test test

::: guidance
third
:::
"""

    no_items_md = """# foo

test test test
"""

    action: RemoveGuidanceAction = RemoveGuidanceAction("1.1.g1")
    check_against_md(three_items_md, action, two_items_md)
    check_against_md(two_items_md, action, one_item_md)
    check_against_md(one_item_md, action, no_items_md)
