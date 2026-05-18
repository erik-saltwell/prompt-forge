"""Tests for `shorthand_to_markdown`.

Two groups:
1. Basic shape — verify each shorthand token renders correctly.
2. Markdownlint rule compliance — one test per rule the emitter touches.
"""

from __future__ import annotations

import re

import pytest

from .utils._short_hand import doc_from_shorthand, shorthand_to_markdown, tree_to_shorthand
from .utils._tree_comparison import structural_equal

# ---------------------------------------------------------------------------
# Basic shape
# ---------------------------------------------------------------------------


def test_empty_shorthand_returns_empty() -> None:
    assert shorthand_to_markdown("") == ""


def test_single_paragraph() -> None:
    assert shorthand_to_markdown("p") == "paragraph-0\n"


def test_two_paragraphs() -> None:
    assert shorthand_to_markdown("p p") == "paragraph-0\n\nparagraph-1\n"


def test_heading_with_paragraph() -> None:
    assert shorthand_to_markdown("h1 p") == "# section-0\n\nparagraph-1\n"


def test_nested_sections() -> None:
    assert shorthand_to_markdown("h1 h2 p") == "# section-0\n\n## section-1\n\nparagraph-2\n"


def test_bullet_list() -> None:
    assert shorthand_to_markdown("ul1 ul1") == "- item-0\n- item-1\n"


def test_ordered_list() -> None:
    assert shorthand_to_markdown("ol1 ol1") == "1. item-0\n2. item-1\n"


def test_nested_bullet_list() -> None:
    assert shorthand_to_markdown("ul1 ul2 ul1") == "- item-0\n  - item-1\n- item-2\n"


def test_nested_ordered_inside_bullet() -> None:
    assert shorthand_to_markdown("ul1 ol2 ul1") == "- item-0\n  1. item-1\n- item-2\n"


def test_paragraph_with_example() -> None:
    expected = "paragraph-0\n\n::: examples\nexample-1\n:::\n"
    assert shorthand_to_markdown("p e") == expected


def test_paragraph_with_both_annotations() -> None:
    expected = "paragraph-0\n\n::: examples\nexample-1\n:::\n\n::: guidance\nguidance-2\n:::\n"
    assert shorthand_to_markdown("p e g") == expected


def test_list_item_with_example() -> None:
    expected = "- item-0\n\n  ::: examples\n  example-1\n  :::\n"
    assert shorthand_to_markdown("ul1 e") == expected


def test_code_block() -> None:
    assert shorthand_to_markdown("cb") == "```\ncode-0\n```\n"


def test_blockquote() -> None:
    assert shorthand_to_markdown("bq") == "> blockquote-0\n"


def test_table() -> None:
    assert shorthand_to_markdown("t") == "| col |\n| --- |\n| cell-0 |\n"


def test_unknown_token_raises() -> None:
    with pytest.raises(ValueError):
        shorthand_to_markdown("xyz")


# ---------------------------------------------------------------------------
# Markdownlint rule compliance
#
# Reference: https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md
# One test per rule the shorthand emitter can affect.
# ---------------------------------------------------------------------------


def test_md003_atx_heading_style() -> None:
    out = shorthand_to_markdown("h1 p h2 p h3 p")
    assert "# section-0" in out
    assert "## section-2" in out
    assert "### section-4" in out
    # No setext underlines.
    for line in out.splitlines():
        assert not re.fullmatch(r"=+", line)
        assert not re.fullmatch(r"-+", line)


def test_md004_unordered_marker_is_dash() -> None:
    out = shorthand_to_markdown("ul1 ul1 ul2")
    assert "* " not in out
    assert "+ " not in out
    assert "- item-0" in out
    assert "- item-1" in out
    assert "  - item-2" in out


def test_md005_consistent_same_level_indent() -> None:
    out = shorthand_to_markdown("ul1 ul2 ul2 ul1 ul2 ul2")
    # All depth-2 items must share the same leading indent.
    depth2_indents = {
        len(line) - len(line.lstrip(" ")) for line in out.splitlines() if line.lstrip(" ").startswith("- item-") and line.startswith(" ")
    }
    assert depth2_indents == {2}


def test_md007_nested_bullet_indent_is_two_spaces() -> None:
    out = shorthand_to_markdown("ul1 ul2")
    assert out == "- item-0\n  - item-1\n"


def test_md012_no_multiple_consecutive_blank_lines() -> None:
    out = shorthand_to_markdown("h1 p h2 p ul1 ul1 p cb p t p")
    assert "\n\n\n" not in out


def test_md018_md019_one_space_after_hash() -> None:
    out = shorthand_to_markdown("h1 h2 h3 h4 h5 h6")
    for line in out.splitlines():
        if line.startswith("#"):
            stripped = line.lstrip("#")
            assert stripped.startswith(" "), f"no space after #: {line!r}"
            assert not stripped.startswith("  "), f"multiple spaces after #: {line!r}"


def test_md020_md021_open_atx_only() -> None:
    out = shorthand_to_markdown("h1 p h2 p")
    for line in out.splitlines():
        if line.startswith("#"):
            # No closing `#` characters at end of heading line.
            assert not re.search(r"\s#+\s*$", line), f"closed ATX: {line!r}"


def test_md022_headings_surrounded_by_blank_lines() -> None:
    out = shorthand_to_markdown("p h2 p")
    lines = out.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("#"):
            assert i == 0 or lines[i - 1] == "", f"no blank line before heading: {line!r}"
            assert i == len(lines) - 1 or lines[i + 1] == "", f"no blank line after heading: {line!r}"


def test_md023_headings_at_line_start() -> None:
    out = shorthand_to_markdown("h1 h2 h3")
    for line in out.splitlines():
        if "#" in line and line.lstrip().startswith("#"):
            assert line.startswith("#"), f"indented heading: {line!r}"


def test_md027_one_space_after_blockquote_marker() -> None:
    out = shorthand_to_markdown("bq")
    for line in out.splitlines():
        if line.startswith(">"):
            # Either ">" alone (blank quoted line) or "> ..." with exactly one space.
            assert line == ">" or line.startswith("> ")
            assert not line.startswith(">  ")


def test_md029_ordered_list_increments_from_one() -> None:
    out = shorthand_to_markdown("ol1 ol1 ol1")
    assert out == "1. item-0\n2. item-1\n3. item-2\n"


def test_md030_one_space_after_list_marker() -> None:
    out = shorthand_to_markdown("ul1 ul1 ol1 ol1")
    for line in out.splitlines():
        stripped = line.lstrip(" ")
        if stripped.startswith("- "):
            assert not stripped.startswith("-  "), f"two spaces after dash: {line!r}"
        m = re.match(r"(\d+)\.\s", stripped)
        if m:
            after = stripped[len(m.group(1)) + 1 :]
            assert after.startswith(" "), f"missing space after ordered marker: {line!r}"
            assert not after.startswith("  "), f"two spaces after ordered marker: {line!r}"


def test_md031_code_block_surrounded_by_blank_lines() -> None:
    out = shorthand_to_markdown("p cb p")
    assert "paragraph-0\n\n```" in out
    assert "```\n\nparagraph-2" in out


def test_md032_lists_surrounded_by_blank_lines() -> None:
    out = shorthand_to_markdown("p ul1 ul1 p")
    assert "paragraph-0\n\n- item-1" in out
    assert "- item-2\n\nparagraph-3" in out


def test_md046_code_blocks_are_fenced() -> None:
    out = shorthand_to_markdown("cb")
    assert out.startswith("```")
    # No 4-space indented code block.
    for line in out.splitlines():
        assert not line.startswith("    "), f"indented code line: {line!r}"


def test_md047_single_trailing_newline() -> None:
    out = shorthand_to_markdown("h1 p")
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_md048_backtick_fences_only() -> None:
    out = shorthand_to_markdown("cb")
    assert "```" in out
    assert "~~~" not in out


def test_md058_table_surrounded_by_blank_lines() -> None:
    out = shorthand_to_markdown("p t p")
    assert "paragraph-0\n\n|" in out
    assert "|\n\nparagraph-2" in out


@pytest.mark.parametrize(
    "shorthand",
    [
        "p",
        "p p",
        "h1",
        "h1 p",
        "h1 p h2 p h2 ul1 ul1 p",
        "h1 ul1 ul2 ul2 ul1",
        "h1 ul1 ol2 ol2 ul1",
        "h1 ul1 ol2 ul3 ol4 ul3",
        "h1 p e g",
        "h1 ul1 e ul1 g ul1",
        "cb bq t",
        "h1 p h2 p h3 p h2 p",
        "ul1 ul1 ul1",
    ],
)
def test_deterministic(shorthand: str) -> None:
    a = doc_from_shorthand(shorthand)
    b = doc_from_shorthand(shorthand)
    assert structural_equal(a, b)


@pytest.mark.parametrize(
    "shorthand",
    [
        "p",
        "p p",
        "h1 p",
        "h1 p h2 p h2 ul1 ul1 p",
        "h1 ul1 ul2 ul2 ul1",
        "h1 ul1 ol2 ol2 ul1",
        "h1 ul1 ol2 ul3 ol4 ul3",
        "h1 p e g",
        "h1 ul1 e ul1 g ul1",
        "cb bq t",
        "h1 p h2 p h3 p h2 p",
        "ul1 ul1 ul1",
    ],
)
def test_round_trip_through_shorthand(shorthand: str) -> None:
    assert tree_to_shorthand(doc_from_shorthand(shorthand)) == shorthand


def test_rejects_unknown_token() -> None:
    with pytest.raises(ValueError, match="unknown shorthand token"):
        doc_from_shorthand("h1 xyz")


def test_rejects_depth_skip() -> None:
    with pytest.raises(ValueError, match="skipped a list-depth level"):
        doc_from_shorthand("h1 ul2")


def test_rejects_annotation_with_no_host() -> None:
    with pytest.raises(ValueError, match="no host"):
        doc_from_shorthand("h1 e")
