from __future__ import annotations

import random

from prompt_model.model import List, ListItem, Paragraph, Section
from prompt_model.service.actions import (
    AddExampleAction,
    AddGuidanceAction,
    RemoveExampleAction,
    RemoveGuidanceAction,
    SkipReason,
    parse_action,
)
from prompt_model.service.actions.anchor import LocationAnchor
from prompt_model.service.parsing.parse_prompt import parse_from_string

from ..utils._short_hand import doc_from_shorthand
from ..utils.actions import Action, check_against_md, check_can_apply, check_undo, check_undo_from_sh

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


# ---------- apply() returns a usable inverse ----------


def test_apply_inverse_restores_only_child_and_recreates_group() -> None:
    tree = parse_from_string("# Title\n\nBody paragraph.\n\n::: examples\nsolo\n:::\n")
    inverse = RemoveExampleAction("1.1.e1").apply(tree)
    section = tree.children[0]
    assert isinstance(section, Section)
    para = section.children[0]
    assert isinstance(para, Paragraph)
    assert para.examples is None  # group torn down
    inverse.apply(tree)
    assert para.examples is not None
    assert [c.text for c in para.examples.children] == ["solo"]


def test_apply_inverse_restores_position_in_list_form_group() -> None:
    tree = parse_from_string("# Title\n\nBody paragraph.\n\n::: examples\n- first\n- middle\n- last\n:::\n")
    inverse = RemoveExampleAction("1.1.e2").apply(tree)
    section = tree.children[0]
    assert isinstance(section, Section)
    para = section.children[0]
    assert isinstance(para, Paragraph)
    assert para.examples is not None
    assert [c.text for c in para.examples.children] == ["first", "last"]
    inverse.apply(tree)
    # Middle annotation reinserted at its original index.
    assert [c.text for c in para.examples.children] == ["first", "middle", "last"]


def test_inverse_apply_returns_callable_redo() -> None:
    tree = parse_from_string("# Title\n\nBody paragraph.\n\n::: examples\nsolo\n:::\n")
    inverse = RemoveExampleAction("1.1.e1").apply(tree)
    redo = inverse.apply(tree)
    section = tree.children[0]
    assert isinstance(section, Section)
    para = section.children[0]
    assert isinstance(para, Paragraph)
    assert para.examples is not None
    redo.apply(tree)
    assert para.examples is None


# ---------- multi-action undo (round-trip via the test util) ----------


def test_undo_single_remove_restores_tree() -> None:
    md = "# Title\n\nBody paragraph.\n\n::: examples\n- a\n- b\n- c\n:::\n"
    check_undo(md, [RemoveExampleAction("1.1.e2")])


def test_undo_remove_last_child_restores_group() -> None:
    md = "# Title\n\nBody paragraph.\n\n::: guidance\nthe only one\n:::\n"
    check_undo(md, [RemoveGuidanceAction("1.1.g1")])


def test_undo_interleaved_add_and_remove_restores_tree() -> None:
    md = "# Title\n\nBody paragraph.\n\n::: examples\n- a\n- b\n:::\n\n::: guidance\n- g1\n- g2\n:::\n"
    actions: list[Action] = [
        RemoveExampleAction("1.1.e1"),
        AddGuidanceAction("1.1", "g3"),
        RemoveGuidanceAction("1.1.g2"),
        AddExampleAction("1.1", "added", anchor=LocationAnchor(kind="first_child", target="1.1")),
    ]
    check_undo(md, actions)


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


def test_remove_undo_1() -> None:
    sh = "h1 p e e e g g"

    check_undo_from_sh(
        sh,
        [
            RemoveExampleAction("1.1.e3"),
            RemoveGuidanceAction("1.1.g2"),
            RemoveExampleAction("1.1.e2"),
            RemoveGuidanceAction("1.1.g1"),
            RemoveExampleAction("1.1.e1"),
        ],
    )


def test_remove_undo_2() -> None:
    sh = "h1 p e e e g g"

    check_undo_from_sh(
        sh,
        [
            RemoveExampleAction("1.1.e3"),
            RemoveGuidanceAction("1.1.g1"),
            RemoveExampleAction("1.1.e2"),
            RemoveGuidanceAction("1.1.g2"),  # ids are frozen so g2 is still g2
            RemoveExampleAction("1.1.e1"),
        ],
    )


def test_remove_undo_3() -> None:
    sh = "h1 p e e e e e e e g g g g g"

    check_undo_from_sh(
        sh,
        [
            RemoveExampleAction("1.1.e5"),
            RemoveExampleAction("1.1.e3"),
            RemoveExampleAction("1.1.e6"),
            RemoveExampleAction("1.1.e4"),
            RemoveExampleAction("1.1.e1"),
            RemoveExampleAction("1.1.e7"),
            RemoveExampleAction("1.1.e2"),
        ],
    )


def test_random_undo() -> None:
    for _ in range(1000):
        e_count: int = 9
        sh = "h1 p"
        e_ids: list[int] = []
        for idx in range(e_count):
            e_ids.append(idx + 1)
            sh = sh + " e"

        random.shuffle(e_ids)
        actions: list[Action] = []
        for idx in range(e_count):
            actions.append(RemoveExampleAction(annotation_id=f"1.1.e{e_ids[idx]}"))
        check_undo_from_sh(shorthand=sh, actions=actions)
