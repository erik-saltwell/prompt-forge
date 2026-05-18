"""Roundtrip stability tests.

parse(md) -> render -> parse -> render
Must produce structurally equal trees AND identical canonical markdown
on the second render.
"""

from __future__ import annotations

from .utils.generation_utils import assert_markdown_roundtrips, assert_shorthand_roundtrips


def test_paragraph() -> None:
    assert_markdown_roundtrips("just some prose")


def test_two_paragraphs() -> None:
    assert_markdown_roundtrips("first para\n\nsecond para")


def test_h1_with_body() -> None:
    assert_markdown_roundtrips("# Title\nsome prose")


def test_nested_sections() -> None:
    assert_markdown_roundtrips("# A\nintro\n\n## B\nsub\n\n### C\ndeep\n\n## D\nback up")


def test_bullet_list() -> None:
    assert_markdown_roundtrips("# h\n- one\n- two")


def test_ordered_list() -> None:
    assert_markdown_roundtrips("# h\n1. one\n2. two")


def test_nested_bullet_list() -> None:
    assert_markdown_roundtrips("# h\n- outer1\n  - inner1\n  - inner2\n- outer2")


def test_ordered_nested_in_bullet() -> None:
    assert_markdown_roundtrips("# h\n- outer\n  1. i1\n  2. i2\n- next")


def test_paragraph_with_example() -> None:
    assert_markdown_roundtrips("# h\nbody\n\n::: examples\nex\n:::")


def test_paragraph_with_guidance() -> None:
    assert_markdown_roundtrips("# h\nbody\n\n::: guidance\nbe brief\n:::")


def test_paragraph_with_both_annotations() -> None:
    assert_markdown_roundtrips("# h\nbody\n\n::: examples\nex\n:::\n\n::: guidance\ng\n:::")


def test_list_item_with_example() -> None:
    assert_markdown_roundtrips("# h\n- item one\n\n  ::: examples\n  ex\n  :::\n- item two")


def test_code_block_with_info() -> None:
    assert_markdown_roundtrips("# h\n\n```python\nprint(1)\n```")


def test_code_block_no_info() -> None:
    assert_markdown_roundtrips("# h\n\n```\nplain code\n```")


def test_blockquote_single_line() -> None:
    assert_markdown_roundtrips("# h\n\n> a quote")


def test_simple_table() -> None:
    assert_markdown_roundtrips("# h\n\n| a | b |\n|---|---|\n| 1 | 2 |")


def test_table_with_multiple_rows() -> None:
    src = "# h\n\n| col1 | col2 |\n|------|------|\n| a    | b    |\n| c    | d    |"
    assert_markdown_roundtrips(src)


def test_combined_doc() -> None:
    src = "# Top\nintro paragraph\n\n## A\n- one\n- two\n  - nested\n\n## B\nbody\n\n::: guidance\nbe concise\n:::"
    assert_markdown_roundtrips(src)


def test_simple_shorthand_roundtrips() -> None:
    sh = "h1 p h2 ul1 ul2 ul1 p"
    assert_shorthand_roundtrips(sh)


def test_ul1_e_g_ul2_shorthand_roundtrips() -> None:
    sh = "ul1 e g ul2"
    assert_shorthand_roundtrips(sh)
