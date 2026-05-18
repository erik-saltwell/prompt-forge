"""Exact-text tests: build a model, render, compare to canonical markdown string."""

from __future__ import annotations

from prompt_model.model import (
    Blockquote,
    CodeBlock,
    Document,
    ExampleAnnotation,
    GuidanceAnnotation,
    List,
    ListItem,
    Paragraph,
    Section,
)

from .utils.generation_utils import assert_markdown_renders_to, assert_renders_to

# ---------------------------------------------------------------------------
# Leaf nodes (constructed directly so the test owns the exact tree shape)
# ---------------------------------------------------------------------------


def test_paragraph_renders_text() -> None:
    assert_renders_to(Paragraph(text="hello world"), "hello world")


def test_code_block_with_info() -> None:
    cb = CodeBlock(info="python", text="print(1)\n")
    assert_renders_to(cb, "```python\nprint(1)\n```")


def test_code_block_no_info() -> None:
    cb = CodeBlock(info="", text="plain\n")
    assert_renders_to(cb, "```\nplain\n```")


def test_blockquote_single_line() -> None:
    assert_renders_to(Blockquote(text="a quote"), "> a quote")


def test_blockquote_multi_line() -> None:
    assert_renders_to(
        Blockquote(text="first\nsecond"),
        "> first\n> second",
    )


# ---------------------------------------------------------------------------
# Section + paragraph
# ---------------------------------------------------------------------------


def test_h1_with_paragraph() -> None:
    section = Section(level=1, text="Title", children=[Paragraph(text="body")])
    assert_renders_to(section, "# Title\n\nbody")


def test_nested_sections() -> None:
    doc = Document(
        children=[
            Section(
                level=1,
                text="A",
                children=[
                    Paragraph(text="intro"),
                    Section(level=2, text="B", children=[Paragraph(text="sub")]),
                ],
            )
        ]
    )
    assert_renders_to(doc, "# A\n\nintro\n\n## B\n\nsub\n")


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


def test_bullet_list_flat() -> None:
    lst = List(
        ordered=False,
        children=[ListItem(text="one"), ListItem(text="two")],
    )
    assert_renders_to(lst, "- one\n- two")


def test_ordered_list_flat() -> None:
    lst = List(
        ordered=True,
        children=[ListItem(text="one"), ListItem(text="two")],
    )
    assert_renders_to(lst, "1. one\n2. two")


def test_nested_bullet_list() -> None:
    inner = List(ordered=False, children=[ListItem(text="i1"), ListItem(text="i2")])
    outer = List(
        ordered=False,
        children=[
            ListItem(text="outer1", children=[inner]),
            ListItem(text="outer2"),
        ],
    )
    assert_renders_to(outer, "- outer1\n  - i1\n  - i2\n- outer2")


def test_ordered_nested_in_bullet() -> None:
    inner = List(ordered=True, children=[ListItem(text="i1"), ListItem(text="i2")])
    outer = List(ordered=False, children=[ListItem(text="o", children=[inner])])
    assert_renders_to(outer, "- o\n  1. i1\n  2. i2")


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------


def test_example_annotation() -> None:
    assert_renders_to(ExampleAnnotation(text="ex body"), "::: examples\nex body\n:::")


def test_guidance_annotation() -> None:
    assert_renders_to(GuidanceAnnotation(text="be brief"), "::: guidance\nbe brief\n:::")


def test_paragraph_with_example_and_guidance() -> None:
    para = Paragraph(
        text="some prose",
        example=ExampleAnnotation(text="ex"),
        guidance=GuidanceAnnotation(text="g"),
    )
    assert_renders_to(
        para,
        "some prose\n\n::: examples\nex\n:::\n\n::: guidance\ng\n:::",
    )


def test_list_item_with_example_indented() -> None:
    lst = List(
        ordered=False,
        children=[
            ListItem(text="item one", example=ExampleAnnotation(text="ex")),
            ListItem(text="item two"),
        ],
    )
    assert_renders_to(
        lst,
        "- item one\n\n  ::: examples\n  ex\n  :::\n- item two",
    )


# ---------------------------------------------------------------------------
# Parse-then-render: source markdown -> canonical markdown
# ---------------------------------------------------------------------------


def test_parse_then_render_paragraph() -> None:
    assert_markdown_renders_to("just some prose", "just some prose\n")


def test_parse_then_render_h1_with_body() -> None:
    src = "# Title\nsome prose"
    assert_markdown_renders_to(src, "# Title\n\nsome prose\n")


def test_parse_then_render_singular_example_alias_canonicalizes() -> None:
    src = "# h\nbody\n::: example\nex\n:::"
    # `::: example` parses to ExampleAnnotation -> renders as `::: examples`.
    assert_markdown_renders_to(
        src,
        "# h\n\nbody\n\n::: examples\nex\n:::\n",
    )


# ---------------------------------------------------------------------------
# Documented canonicalisations (intentional model collapses).
# ---------------------------------------------------------------------------


def test_indented_code_block_re_emits_as_fenced() -> None:
    # CommonMark indented code blocks (4-space prefix) and fenced code blocks
    # collapse to the same `CodeBlock` node. Re-emit always uses the fenced
    # form, since it's strictly more expressive (can carry an info string).
    src = "some prose\n\n    indented line 1\n    indented line 2"
    assert_markdown_renders_to(
        src,
        "some prose\n\n```\nindented line 1\nindented line 2\n```\n",
    )


def test_ordered_list_start_renumbered_from_one() -> None:
    # Ordered lists are always renumbered starting at 1 on re-emit. Source
    # markers other than 1./2./3. (e.g., starting at 5, or all `1.`) are lost.
    src = "5. first\n6. second\n7. third"
    assert_markdown_renders_to(src, "1. first\n2. second\n3. third\n")


def test_repeated_one_marker_renumbered() -> None:
    # The common "lazy" form where every item is written as `1.` also
    # renumbers — there's no preservation of the original markers.
    src = "1. a\n1. b\n1. c"
    assert_markdown_renders_to(src, "1. a\n2. b\n3. c\n")
