"""Shape tests: parse markdown -> render -> re-parse -> assert shorthand.

These verify that `to_markdown` produces something that re-parses to a tree
with the same structural shape, without committing to an exact text form.
"""

from __future__ import annotations

from .utils.generation_utils import assert_render_matches_shorthand


def test_single_paragraph() -> None:
    assert_render_matches_shorthand("just some prose", "p")


def test_two_paragraphs() -> None:
    assert_render_matches_shorthand("first\n\nsecond", "p p")


def test_h1_with_paragraph() -> None:
    assert_render_matches_shorthand("# Title\nbody", "h1 p")


def test_nested_sections() -> None:
    src = "# A\nintro\n\n## B\nsub\n\n### C\ndeep\n\n## D\nback up"
    assert_render_matches_shorthand(src, "h1 p h2 p h3 p h2 p")


def test_bullet_list() -> None:
    assert_render_matches_shorthand("# h\n- a\n- b", "h1 ul1 ul1")


def test_ordered_list() -> None:
    assert_render_matches_shorthand("# h\n1. a\n2. b", "h1 ol1 ol1")


def test_nested_bullet_list() -> None:
    src = "# h\n- outer1\n  - inner1\n  - inner2\n- outer2"
    assert_render_matches_shorthand(src, "h1 ul1 ul2 ul2 ul1")


def test_ordered_nested_in_bullet() -> None:
    src = "# h\n- outer\n  1. i1\n  2. i2\n- next"
    assert_render_matches_shorthand(src, "h1 ul1 ol2 ol2 ul1")


def test_paragraph_with_example() -> None:
    src = "# h\nbody\n::: examples\nex\n:::"
    assert_render_matches_shorthand(src, "h1 p e")


def test_paragraph_with_both_annotations() -> None:
    src = "# h\nbody\n::: examples\nex\n:::\n\n::: guidance\ng\n:::"
    assert_render_matches_shorthand(src, "h1 p e g")


def test_list_item_with_example() -> None:
    src = "# h\n- item one\n  ::: examples\n  ex\n  :::\n- item two"
    assert_render_matches_shorthand(src, "h1 ul1 e ul1")


def test_code_block_in_section() -> None:
    src = "# h\n```python\nprint(1)\n```"
    assert_render_matches_shorthand(src, "h1 cb")


def test_blockquote_in_section() -> None:
    src = "# h\n> a quote"
    assert_render_matches_shorthand(src, "h1 bq")


def test_combined() -> None:
    src = "# foo\nprose\n\n## bar\n- a\n- b\n  - c\n- d\n\n## gum\n```\nx\n```"
    assert_render_matches_shorthand(src, "h1 p h2 ul1 ul1 ul2 ul1 h2 cb")
