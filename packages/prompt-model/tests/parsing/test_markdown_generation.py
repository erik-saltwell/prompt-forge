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
from prompt_model.service.parsing import parse_from_string

from ..utils import roundtrip as rt
from ..utils.parsing import (
    check_md_against_md,
    check_md_against_sh,
    check_obj_against_md,
)

# ---------------------------------------------------------------------------
# Leaf nodes (constructed directly so the test owns the exact tree shape)
# ---------------------------------------------------------------------------


def test_paragraph_renders_text() -> None:
    check_obj_against_md(Paragraph(text="hello world"), "hello world")


def test_code_block_with_info() -> None:
    cb = CodeBlock(info="python", text="print(1)\n")
    check_obj_against_md(cb, "```python\nprint(1)\n```")


def test_code_block_no_info() -> None:
    cb = CodeBlock(info="", text="plain\n")
    check_obj_against_md(cb, "```\nplain\n```")


def test_blockquote_single_line() -> None:
    check_obj_against_md(Blockquote(text="a quote"), "> a quote")


def test_blockquote_multi_line() -> None:
    check_obj_against_md(
        Blockquote(text="first\nsecond"),
        "> first\n> second",
    )


# ---------------------------------------------------------------------------
# Section + paragraph
# ---------------------------------------------------------------------------


def test_h1_with_paragraph() -> None:
    section = Section(level=1, text="Title", children=[Paragraph(text="body")])
    check_obj_against_md(section, "# Title\n\nbody")


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
    check_obj_against_md(doc, "# A\n\nintro\n\n## B\n\nsub\n")


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


def test_bullet_list_flat() -> None:
    lst = List(
        ordered=False,
        children=[ListItem(text="one"), ListItem(text="two")],
    )
    check_obj_against_md(lst, "- one\n- two")


def test_ordered_list_flat() -> None:
    lst = List(
        ordered=True,
        children=[ListItem(text="one"), ListItem(text="two")],
    )
    check_obj_against_md(lst, "1. one\n2. two")


def test_nested_bullet_list() -> None:
    inner = List(ordered=False, children=[ListItem(text="i1"), ListItem(text="i2")])
    outer = List(
        ordered=False,
        children=[
            ListItem(text="outer1", children=[inner]),
            ListItem(text="outer2"),
        ],
    )
    check_obj_against_md(outer, "- outer1\n  - i1\n  - i2\n- outer2")


def test_ordered_nested_in_bullet() -> None:
    inner = List(ordered=True, children=[ListItem(text="i1"), ListItem(text="i2")])
    outer = List(ordered=False, children=[ListItem(text="o", children=[inner])])
    check_obj_against_md(outer, "- o\n  1. i1\n  2. i2")


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------


def test_example_annotation() -> None:
    check_obj_against_md(ExampleAnnotation(text="ex body"), "::: examples\nex body\n:::")


def test_guidance_annotation() -> None:
    check_obj_against_md(GuidanceAnnotation(text="be brief"), "::: guidance\nbe brief\n:::")


def test_paragraph_with_example_and_guidance() -> None:
    para = Paragraph(
        text="some prose",
        example=ExampleAnnotation(text="ex"),
        guidance=GuidanceAnnotation(text="g"),
    )
    check_obj_against_md(
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
    check_obj_against_md(
        lst,
        "- item one\n\n  ::: examples\n  ex\n  :::\n- item two",
    )


# ---------------------------------------------------------------------------
# Parse-then-render: source markdown -> canonical markdown
# ---------------------------------------------------------------------------


def test_parse_then_render_paragraph() -> None:
    check_md_against_md("just some prose", "just some prose\n")


def test_parse_then_render_h1_with_body() -> None:
    src = "# Title\nsome prose"
    check_md_against_md(src, "# Title\n\nsome prose\n")


def test_parse_then_render_singular_example_alias_canonicalizes() -> None:
    src = "# h\nbody\n::: example\nex\n:::"
    # `::: example` parses to ExampleAnnotation -> renders as `::: examples`.
    check_md_against_md(
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
    check_md_against_md(
        src,
        "some prose\n\n```\nindented line 1\nindented line 2\n```\n",
    )


def test_ordered_list_start_renumbered_from_one() -> None:
    # Ordered lists are always renumbered starting at 1 on re-emit. Source
    # markers other than 1./2./3. (e.g., starting at 5, or all `1.`) are lost.
    src = "5. first\n6. second\n7. third"
    check_md_against_md(src, "1. first\n2. second\n3. third\n")


def test_repeated_one_marker_renumbered() -> None:
    # The common "lazy" form where every item is written as `1.` also
    # renumbers — there's no preservation of the original markers.
    src = "1. a\n1. b\n1. c"
    check_md_against_md(src, "1. a\n2. b\n3. c\n")


# ---------------------------------------------------------------------------
# MD003 — Consistent heading style (we always emit ATX).
# ---------------------------------------------------------------------------


def test_md003_setext_heading_becomes_atx() -> None:
    src = "Title\n=====\n\nbody"
    check_md_against_md(src, "# Title\n\nbody\n")


# ---------------------------------------------------------------------------
# MD004 — Consistent unordered list markers (we always use `-`).
# ---------------------------------------------------------------------------


def test_md004_asterisk_marker_becomes_dash() -> None:
    src = "* a\n* b\n* c"
    check_md_against_md(src, "- a\n- b\n- c\n")


def test_md004_plus_marker_becomes_dash() -> None:
    src = "+ a\n+ b"
    check_md_against_md(src, "- a\n- b\n")


# ---------------------------------------------------------------------------
# MD005 — Consistent same-level indentation.
# ---------------------------------------------------------------------------


def test_md005_nested_list_uses_uniform_indent() -> None:
    src = "- outer\n  - inner1\n   - inner2"
    # Both inner items should land at the same indent in the output.
    check_md_against_md(src, "- outer\n  - inner1\n  - inner2\n")


# ---------------------------------------------------------------------------
# MD007 — Unordered list indent of 2 spaces.
# ---------------------------------------------------------------------------


def test_md007_nested_bullet_indent_is_two_spaces() -> None:
    src = "- outer\n    - inner"
    check_md_against_md(src, "- outer\n  - inner\n")


# ---------------------------------------------------------------------------
# MD012 — No multiple consecutive blank lines.
# ---------------------------------------------------------------------------


def test_md012_extra_blank_lines_collapse() -> None:
    src = "first para\n\n\n\nsecond para"
    check_md_against_md(src, "first para\n\nsecond para\n")


# ---------------------------------------------------------------------------
# MD018 — One space after `#`.
# ---------------------------------------------------------------------------


def test_md018_no_space_after_hash_gets_one() -> None:
    # `#Title` with no space is not even a heading in CommonMark, so the
    # closest test is verifying we always emit exactly one space.
    src = "#  Title"
    check_md_against_md(src, "# Title\n")


# ---------------------------------------------------------------------------
# MD019 — No multiple spaces after `#`.
# ---------------------------------------------------------------------------


def test_md019_multiple_spaces_after_hash_collapse() -> None:
    src = "##    Heading"
    check_md_against_md(src, "## Heading\n")


# ---------------------------------------------------------------------------
# MD020 / MD021 — No closed ATX headings.
# ---------------------------------------------------------------------------


def test_md020_md021_closed_atx_becomes_open() -> None:
    src = "# Title #\n\nbody"
    check_md_against_md(src, "# Title\n\nbody\n")


# ---------------------------------------------------------------------------
# MD022 — Headings surrounded by blank lines.
# ---------------------------------------------------------------------------


def test_md022_heading_gets_blank_lines_around() -> None:
    src = "intro\n# Title\nbody"
    check_md_against_md(src, "intro\n\n# Title\n\nbody\n")


# ---------------------------------------------------------------------------
# MD023 — Headings at line start.
# ---------------------------------------------------------------------------


def test_md023_indented_heading_unindented() -> None:
    # Markdown-it parses `  # title` (1-3 spaces) as a heading; we emit it
    # at column 0.
    src = "   # Title\n\nbody"
    check_md_against_md(src, "# Title\n\nbody\n")


# ---------------------------------------------------------------------------
# MD027 — One space after `>` in blockquotes.
# ---------------------------------------------------------------------------


def test_md027_blockquote_one_space_after_marker() -> None:
    # Built directly so the parser's blockquote-flattening doesn't muddy the
    # test. Demonstrates the canonical `> {line}` form on output.
    bq = Blockquote(text="a quote\nsecond line")
    check_obj_against_md(bq, "> a quote\n> second line")


# ---------------------------------------------------------------------------
# MD029 — Ordered list prefix style (1, 2, 3, …).
# ---------------------------------------------------------------------------


def test_md029_renumbers_from_one() -> None:
    src = "1. a\n1. b\n1. c"
    check_md_against_md(src, "1. a\n2. b\n3. c\n")


# ---------------------------------------------------------------------------
# MD030 — One space after list marker.
# ---------------------------------------------------------------------------


def test_md030_one_space_after_marker() -> None:
    src = "-   a\n-   b"
    check_md_against_md(src, "- a\n- b\n")


# ---------------------------------------------------------------------------
# MD031 — Fenced code blocks surrounded by blank lines (including in lists).
# ---------------------------------------------------------------------------


def test_md031_code_block_at_top_level_has_blank_lines() -> None:
    src = "intro\n\n```python\nprint(1)\n```\n\noutro"
    check_md_against_md(
        src,
        "intro\n\n```python\nprint(1)\n```\n\noutro\n",
    )


def test_md031_code_block_inside_list_makes_list_loose() -> None:
    # Per MD031 default (`list_items: true`), a fenced code block inside a
    # list item requires blank lines around it — which forces the list loose.
    src = "- item one\n  ```\n  code\n  ```\n- item two"
    rendered = parse_from_string(src).to_markdown()
    # Blank line between closing fence (indented) and the next list marker.
    assert "  ```\n\n- item two" in rendered


# ---------------------------------------------------------------------------
# MD032 — Lists surrounded by blank lines.
# ---------------------------------------------------------------------------


def test_md032_list_surrounded_by_blank_lines() -> None:
    # Built directly because CommonMark's lazy continuation would otherwise
    # absorb `outro` into the last list item. The rule we're verifying is
    # purely about output: list-as-sibling always gets blank lines around it.
    doc = Document(
        children=[
            Paragraph(text="intro"),
            List(
                ordered=False,
                children=[ListItem(text="a"), ListItem(text="b")],
            ),
            Paragraph(text="outro"),
        ]
    )
    check_obj_against_md(doc, "intro\n\n- a\n- b\n\noutro\n")


# ---------------------------------------------------------------------------
# MD040 — Specify language on fenced code blocks (intentional violation).
# ---------------------------------------------------------------------------


def test_md040_empty_info_string_is_emitted_as_is() -> None:
    # Documented exception to markdownlint: when the source has no language
    # info (or was an indented code block), we emit a bare ``` fence rather
    # than inventing a language string we don't know.
    src = "```\nplain\n```"
    check_md_against_md(src, "```\nplain\n```\n")


# ---------------------------------------------------------------------------
# MD046 — Consistent code block style (always fenced).
# ---------------------------------------------------------------------------


def test_md046_indented_code_block_becomes_fenced() -> None:
    src = "intro\n\n    indented code"
    check_md_against_md(src, "intro\n\n```\nindented code\n```\n")


# ---------------------------------------------------------------------------
# MD047 — Files end with exactly one trailing newline.
# ---------------------------------------------------------------------------


def test_md047_output_ends_with_single_newline() -> None:
    rendered = parse_from_string("just some prose").to_markdown()
    assert rendered.endswith("\n")
    assert not rendered.endswith("\n\n")


def test_md047_no_trailing_newline_input_still_gets_one() -> None:
    src = "# Title\n\nbody"  # no trailing newline
    rendered = parse_from_string(src).to_markdown()
    assert rendered.endswith("body\n")


# ---------------------------------------------------------------------------
# MD048 — Consistent code fence style (always backticks).
# ---------------------------------------------------------------------------


def test_md048_tilde_fence_becomes_backtick() -> None:
    src = "~~~python\nprint(1)\n~~~"
    check_md_against_md(src, "```python\nprint(1)\n```\n")


# ---------------------------------------------------------------------------
# MD058 — Tables surrounded by blank lines.
# ---------------------------------------------------------------------------


def test_md058_table_surrounded_by_blank_lines() -> None:
    src = "intro\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\noutro"
    check_md_against_md(
        src,
        "intro\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\noutro\n",
    )


def test_paragraph() -> None:
    rt.md_obj_md_obj_md("just some prose")


def test_two_paragraphs() -> None:
    rt.md_obj_md_obj_md("first para\n\nsecond para")


def test_h1_with_body() -> None:
    rt.md_obj_md_obj_md("# Title\nsome prose")


def test_nested_sections_md() -> None:
    rt.md_obj_md_obj_md("# A\nintro\n\n## B\nsub\n\n### C\ndeep\n\n## D\nback up")


def test_bullet_list() -> None:
    rt.md_obj_md_obj_md("# h\n- one\n- two")


def test_ordered_list() -> None:
    rt.md_obj_md_obj_md("# h\n1. one\n2. two")


def test_nested_bullet_list_md() -> None:
    rt.md_obj_md_obj_md("# h\n- outer1\n  - inner1\n  - inner2\n- outer2")


def test_ordered_nested_in_bullet_md() -> None:
    rt.md_obj_md_obj_md("# h\n- outer\n  1. i1\n  2. i2\n- next")


def test_paragraph_with_example() -> None:
    rt.md_obj_md_obj_md("# h\nbody\n\n::: examples\nex\n:::")


def test_paragraph_with_guidance() -> None:
    rt.md_obj_md_obj_md("# h\nbody\n\n::: guidance\nbe brief\n:::")


def test_paragraph_with_both_annotations() -> None:
    rt.md_obj_md_obj_md("# h\nbody\n\n::: examples\nex\n:::\n\n::: guidance\ng\n:::")


def test_list_item_with_example() -> None:
    rt.md_obj_md_obj_md("# h\n- item one\n\n  ::: examples\n  ex\n  :::\n- item two")


def test_code_block_with_info_md() -> None:
    rt.md_obj_md_obj_md("# h\n\n```python\nprint(1)\n```")


def test_code_block_no_info_md() -> None:
    rt.md_obj_md_obj_md("# h\n\n```\nplain code\n```")


def test_blockquote_single_line_md() -> None:
    rt.md_obj_md_obj_md("# h\n\n> a quote")


def test_simple_table() -> None:
    rt.md_obj_md_obj_md("# h\n\n| a | b |\n|---|---|\n| 1 | 2 |")


def test_table_with_multiple_rows() -> None:
    src = "# h\n\n| col1 | col2 |\n|------|------|\n| a    | b    |\n| c    | d    |"
    rt.md_obj_md_obj_md(src)


def test_combined_doc() -> None:
    src = "# Top\nintro paragraph\n\n## A\n- one\n- two\n  - nested\n\n## B\nbody\n\n::: guidance\nbe concise\n:::"
    rt.md_obj_md_obj_md(src)


def test_simple_shorthand_roundtrips() -> None:
    sh = "h1 p h2 ul1 ul2 ul1 p"
    rt.sh_obj_md_obj_sh(sh)


def test_ul1_e_g_ul2_shorthand_roundtrips() -> None:
    sh = "ul1 e g ul2"
    rt.sh_obj_md_obj_sh(sh)


def test_single_paragraph() -> None:
    check_md_against_sh("just some prose", "p")


def test_two_paragraphs_sh() -> None:
    check_md_against_sh("first\n\nsecond", "p p")


def test_h1_with_paragraph_sh() -> None:
    check_md_against_sh("# Title\nbody", "h1 p")


def test_nested_sections_sh() -> None:
    src = "# A\nintro\n\n## B\nsub\n\n### C\ndeep\n\n## D\nback up"
    check_md_against_sh(src, "h1 p h2 p h3 p h2 p")


def test_bullet_list_sh() -> None:
    check_md_against_sh("# h\n- a\n- b", "h1 ul1 ul1")


def test_ordered_list_sh() -> None:
    check_md_against_sh("# h\n1. a\n2. b", "h1 ol1 ol1")


def test_nested_bullet_list_sh() -> None:
    src = "# h\n- outer1\n  - inner1\n  - inner2\n- outer2"
    check_md_against_sh(src, "h1 ul1 ul2 ul2 ul1")


def test_ordered_nested_in_bullet_sh() -> None:
    src = "# h\n- outer\n  1. i1\n  2. i2\n- next"
    check_md_against_sh(src, "h1 ul1 ol2 ol2 ul1")


def test_paragraph_with_example_sh() -> None:
    src = "# h\nbody\n::: examples\nex\n:::"
    check_md_against_sh(src, "h1 p e")


def test_paragraph_with_both_annotations_sh() -> None:
    src = "# h\nbody\n::: examples\nex\n:::\n\n::: guidance\ng\n:::"
    check_md_against_sh(src, "h1 p e g")


def test_list_item_with_example_sh() -> None:
    src = "# h\n- item one\n  ::: examples\n  ex\n  :::\n- item two"
    check_md_against_sh(src, "h1 ul1 e ul1")


def test_code_block_in_section() -> None:
    src = "# h\n```python\nprint(1)\n```"
    check_md_against_sh(src, "h1 cb")


def test_blockquote_in_section() -> None:
    src = "# h\n> a quote"
    check_md_against_sh(src, "h1 bq")


def test_combined() -> None:
    src = "# foo\nprose\n\n## bar\n- a\n- b\n  - c\n- d\n\n## gum\n```\nx\n```"
    check_md_against_sh(src, "h1 p h2 ul1 ul1 ul2 ul1 h2 cb")
