"""Markdownlint compliance tests.

Standard: https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md

Each test follows the same shape: provide a non-canonical input, parse, render,
and assert the rendered output is canonical-form and conformant with the named
rule. One test per formatting-relevant rule.

Two rules are intentional violations and tested as such:
- MD040 (specify code-block language): we emit empty info when info is unknown.
"""

from __future__ import annotations

from prompt_model.model import (
    Blockquote,
    Document,
    List,
    ListItem,
    Paragraph,
)
from prompt_model.service.parsing.parse_prompt import parse_from_string

from .utils.generation_utils import assert_markdown_renders_to, assert_renders_to

# ---------------------------------------------------------------------------
# MD003 — Consistent heading style (we always emit ATX).
# ---------------------------------------------------------------------------


def test_md003_setext_heading_becomes_atx() -> None:
    src = "Title\n=====\n\nbody"
    assert_markdown_renders_to(src, "# Title\n\nbody\n")


# ---------------------------------------------------------------------------
# MD004 — Consistent unordered list markers (we always use `-`).
# ---------------------------------------------------------------------------


def test_md004_asterisk_marker_becomes_dash() -> None:
    src = "* a\n* b\n* c"
    assert_markdown_renders_to(src, "- a\n- b\n- c\n")


def test_md004_plus_marker_becomes_dash() -> None:
    src = "+ a\n+ b"
    assert_markdown_renders_to(src, "- a\n- b\n")


# ---------------------------------------------------------------------------
# MD005 — Consistent same-level indentation.
# ---------------------------------------------------------------------------


def test_md005_nested_list_uses_uniform_indent() -> None:
    src = "- outer\n  - inner1\n   - inner2"
    # Both inner items should land at the same indent in the output.
    assert_markdown_renders_to(src, "- outer\n  - inner1\n  - inner2\n")


# ---------------------------------------------------------------------------
# MD007 — Unordered list indent of 2 spaces.
# ---------------------------------------------------------------------------


def test_md007_nested_bullet_indent_is_two_spaces() -> None:
    src = "- outer\n    - inner"
    assert_markdown_renders_to(src, "- outer\n  - inner\n")


# ---------------------------------------------------------------------------
# MD012 — No multiple consecutive blank lines.
# ---------------------------------------------------------------------------


def test_md012_extra_blank_lines_collapse() -> None:
    src = "first para\n\n\n\nsecond para"
    assert_markdown_renders_to(src, "first para\n\nsecond para\n")


# ---------------------------------------------------------------------------
# MD018 — One space after `#`.
# ---------------------------------------------------------------------------


def test_md018_no_space_after_hash_gets_one() -> None:
    # `#Title` with no space is not even a heading in CommonMark, so the
    # closest test is verifying we always emit exactly one space.
    src = "#  Title"
    assert_markdown_renders_to(src, "# Title\n")


# ---------------------------------------------------------------------------
# MD019 — No multiple spaces after `#`.
# ---------------------------------------------------------------------------


def test_md019_multiple_spaces_after_hash_collapse() -> None:
    src = "##    Heading"
    assert_markdown_renders_to(src, "## Heading\n")


# ---------------------------------------------------------------------------
# MD020 / MD021 — No closed ATX headings.
# ---------------------------------------------------------------------------


def test_md020_md021_closed_atx_becomes_open() -> None:
    src = "# Title #\n\nbody"
    assert_markdown_renders_to(src, "# Title\n\nbody\n")


# ---------------------------------------------------------------------------
# MD022 — Headings surrounded by blank lines.
# ---------------------------------------------------------------------------


def test_md022_heading_gets_blank_lines_around() -> None:
    src = "intro\n# Title\nbody"
    assert_markdown_renders_to(src, "intro\n\n# Title\n\nbody\n")


# ---------------------------------------------------------------------------
# MD023 — Headings at line start.
# ---------------------------------------------------------------------------


def test_md023_indented_heading_unindented() -> None:
    # Markdown-it parses `  # title` (1-3 spaces) as a heading; we emit it
    # at column 0.
    src = "   # Title\n\nbody"
    assert_markdown_renders_to(src, "# Title\n\nbody\n")


# ---------------------------------------------------------------------------
# MD027 — One space after `>` in blockquotes.
# ---------------------------------------------------------------------------


def test_md027_blockquote_one_space_after_marker() -> None:
    # Built directly so the parser's blockquote-flattening doesn't muddy the
    # test. Demonstrates the canonical `> {line}` form on output.
    bq = Blockquote(text="a quote\nsecond line")
    assert_renders_to(bq, "> a quote\n> second line")


# ---------------------------------------------------------------------------
# MD029 — Ordered list prefix style (1, 2, 3, …).
# ---------------------------------------------------------------------------


def test_md029_renumbers_from_one() -> None:
    src = "1. a\n1. b\n1. c"
    assert_markdown_renders_to(src, "1. a\n2. b\n3. c\n")


# ---------------------------------------------------------------------------
# MD030 — One space after list marker.
# ---------------------------------------------------------------------------


def test_md030_one_space_after_marker() -> None:
    src = "-   a\n-   b"
    assert_markdown_renders_to(src, "- a\n- b\n")


# ---------------------------------------------------------------------------
# MD031 — Fenced code blocks surrounded by blank lines (including in lists).
# ---------------------------------------------------------------------------


def test_md031_code_block_at_top_level_has_blank_lines() -> None:
    src = "intro\n\n```python\nprint(1)\n```\n\noutro"
    assert_markdown_renders_to(
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
    assert_renders_to(doc, "intro\n\n- a\n- b\n\noutro\n")


# ---------------------------------------------------------------------------
# MD040 — Specify language on fenced code blocks (intentional violation).
# ---------------------------------------------------------------------------


def test_md040_empty_info_string_is_emitted_as_is() -> None:
    # Documented exception to markdownlint: when the source has no language
    # info (or was an indented code block), we emit a bare ``` fence rather
    # than inventing a language string we don't know.
    src = "```\nplain\n```"
    assert_markdown_renders_to(src, "```\nplain\n```\n")


# ---------------------------------------------------------------------------
# MD046 — Consistent code block style (always fenced).
# ---------------------------------------------------------------------------


def test_md046_indented_code_block_becomes_fenced() -> None:
    src = "intro\n\n    indented code"
    assert_markdown_renders_to(src, "intro\n\n```\nindented code\n```\n")


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
    assert_markdown_renders_to(src, "```python\nprint(1)\n```\n")


# ---------------------------------------------------------------------------
# MD058 — Tables surrounded by blank lines.
# ---------------------------------------------------------------------------


def test_md058_table_surrounded_by_blank_lines() -> None:
    src = "intro\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\noutro"
    assert_markdown_renders_to(
        src,
        "intro\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\noutro\n",
    )
