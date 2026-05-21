from __future__ import annotations

import pytest
from prompt_model.prompt import PromptErrorType
from prompt_model.prompt.validation import find_errors_from_string
from prompt_model.prompt.validation.clean_prompt import clean_prompt_from_string

from ..utils.cleaning import (
    ExpectedAction,
    check_cleaning_from_md,
    check_no_cleaning,
)
from ..utils.validation import check_no_errors_from_md

# A minimal valid body so the cleaned output passes the validator's
# `first_heading_is_h1` and `markdown_not_empty` rules without distracting from
# the line-ending behavior we're actually testing.
_BODY = "# Title\n\nA paragraph.\n"


# ---------------------------------------------------------------------------
# Section 1 — NormalizeLineEndings
# ---------------------------------------------------------------------------


def test_crlf_is_converted_to_lf() -> None:
    crlf_body = _BODY.replace("\n", "\r\n")
    check_cleaning_from_md(
        input_markdown=crlf_body,
        expected_markdown=_BODY,
        expected_actions=[ExpectedAction(line_no=None, description_contains="CRLF")],
    )


def test_lone_cr_is_converted_to_lf() -> None:
    cr_body = _BODY.replace("\n", "\r")
    check_cleaning_from_md(
        input_markdown=cr_body,
        expected_markdown=_BODY,
        expected_actions=[ExpectedAction(line_no=None, description_contains="line endings")],
    )


def test_mixed_crlf_and_lf_collapse_to_lf() -> None:
    # First newline is CRLF, the rest are LF; result is uniform LF and we
    # report exactly one action (whole-document normalization).
    mixed = "# Title\r\n\nA paragraph.\n"
    check_cleaning_from_md(
        input_markdown=mixed,
        expected_markdown=_BODY,
        expected_actions=[ExpectedAction(line_no=None, description_contains="line endings")],
    )


def test_pure_lf_is_a_no_op() -> None:
    check_no_cleaning(_BODY)


# ---------------------------------------------------------------------------
# Section 2 — AddSpaceAfterFenceColons
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("word", ["examples", "example", "guidance"])
def test_missing_space_after_fence_colons_is_inserted(word: str) -> None:
    input_md = f"# Title\n\nA host paragraph.\n\n:::{word}\nbody text\n:::\n"
    expected_md = f"# Title\n\nA host paragraph.\n\n::: {word}\nbody text\n:::\n"
    check_cleaning_from_md(
        input_markdown=input_md,
        expected_markdown=expected_md,
        expected_actions=[ExpectedAction(line_no=5, description_contains="missing space")],
    )


def test_fence_word_casing_is_preserved() -> None:
    # We insert the space but never alter the author's casing. The resulting
    # `::: Examples` is not a recognized fence (parser is case-sensitive on
    # the fence word) so we opt out of output validation here — this test is
    # specifically about the casing-preservation invariant.
    input_md = "# Title\n\nA host paragraph.\n\n:::Examples\nbody text\n:::\n"
    expected_md = "# Title\n\nA host paragraph.\n\n::: Examples\nbody text\n:::\n"
    check_cleaning_from_md(
        input_markdown=input_md,
        expected_markdown=expected_md,
        expected_actions=[ExpectedAction(line_no=5, description_contains="missing space")],
        validate_output=False,
    )


def test_inline_fence_shape_is_not_touched() -> None:
    # `:::examples` mid-line is not at line start — never a fence open.
    check_no_cleaning("# Title\n\nSee :::examples in the docs for details.\n")


def test_fence_shape_inside_code_block_is_not_touched() -> None:
    check_no_cleaning("# Title\n\nA paragraph.\n\n```\n:::examples\n```\n")


def test_unrelated_triple_colon_directive_is_not_touched() -> None:
    # `:::warning` is not one of our three recognized fence words.
    check_no_cleaning("# Title\n\nA paragraph.\n\n:::warning\nstuff\n:::\n")


# ---------------------------------------------------------------------------
# Section 3 — DedentTopLevelFence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("indent", [" ", "  ", "   "])
def test_one_to_three_space_indent_is_stripped(indent: str) -> None:
    input_md = f"# Title\n\nA host paragraph.\n\n{indent}::: examples\ne1\n:::\n"
    expected_md = "# Title\n\nA host paragraph.\n\n::: examples\ne1\n:::\n"
    check_cleaning_from_md(
        input_markdown=input_md,
        expected_markdown=expected_md,
        expected_actions=[ExpectedAction(line_no=5, description_contains="leading indent")],
    )


def test_four_space_indent_is_left_alone() -> None:
    # At 4+ spaces we can't tell intentional code/nesting from accidental
    # indent, so we punt and let the validator flag it via
    # NoAnnotationFenceInParagraph.
    check_no_cleaning("# Title\n\nA host paragraph.\n\n    ::: examples\ne1\n:::\n")


def test_indent_after_list_item_is_preserved() -> None:
    # `  ::: examples` after `- item` is properly-nested annotation content;
    # dedenting would eject the directive from the list item's scope.
    input_md = "# Title\n\n- a list item\n\n  ::: examples\n  e1\n  :::\n"
    check_no_cleaning(input_md)


def test_dedent_fires_at_document_start() -> None:
    # No prior non-blank line ⇒ dedent still applies. The result is an orphan
    # annotation that fails validation, so we opt out of output validation —
    # this test is about the dedent guard, not about producing a valid doc.
    input_md = "  ::: examples\ne1\n:::\n"
    expected_md = "::: examples\ne1\n:::\n"
    check_cleaning_from_md(
        input_markdown=input_md,
        expected_markdown=expected_md,
        expected_actions=[ExpectedAction(line_no=1, description_contains="leading indent")],
        validate_output=False,
    )


def test_indented_fence_inside_code_block_is_not_touched() -> None:
    check_no_cleaning("# Title\n\nA paragraph.\n\n```\n  ::: examples\n```\n")


def test_dedent_matches_fence_word_case_insensitively() -> None:
    # The dedent regex must match the same casings the space-inserter
    # accepts, otherwise `:::Examples` would get the space but keep its
    # indent. Result fails validation (case-sensitive fence parsing), so we
    # opt out of output validation.
    input_md = "# Title\n\nA host paragraph.\n\n  ::: Examples\ne1\n:::\n"
    expected_md = "# Title\n\nA host paragraph.\n\n::: Examples\ne1\n:::\n"
    check_cleaning_from_md(
        input_markdown=input_md,
        expected_markdown=expected_md,
        expected_actions=[ExpectedAction(line_no=5, description_contains="leading indent")],
        validate_output=False,
    )


# ---------------------------------------------------------------------------
# Section 4 — AddBlankLineAroundFence
# ---------------------------------------------------------------------------


def test_blank_line_inserted_before_open_fence() -> None:
    input_md = "# Title\n\nA host paragraph.\n::: examples\ne1\n:::\n"
    expected_md = "# Title\n\nA host paragraph.\n\n::: examples\ne1\n:::\n"
    check_cleaning_from_md(
        input_markdown=input_md,
        expected_markdown=expected_md,
        expected_actions=[ExpectedAction(line_no=4, description_contains="blank line before")],
    )


def test_blank_line_inserted_after_close_fence() -> None:
    input_md = "# Title\n\nA host paragraph.\n\n::: examples\ne1\n:::\nNext paragraph.\n"
    expected_md = "# Title\n\nA host paragraph.\n\n::: examples\ne1\n:::\n\nNext paragraph.\n"
    check_cleaning_from_md(
        input_markdown=input_md,
        expected_markdown=expected_md,
        expected_actions=[ExpectedAction(line_no=7, description_contains="blank line after")],
    )


def test_both_before_open_and_after_close_fire_together() -> None:
    input_md = "# Title\n\nA host paragraph.\n::: examples\ne1\n:::\nNext paragraph.\n"
    expected_md = "# Title\n\nA host paragraph.\n\n::: examples\ne1\n:::\n\nNext paragraph.\n"
    check_cleaning_from_md(
        input_markdown=input_md,
        expected_markdown=expected_md,
        expected_actions=[
            ExpectedAction(line_no=4, description_contains="blank line before"),
            ExpectedAction(line_no=6, description_contains="blank line after"),
        ],
    )


def test_already_separated_fences_are_a_no_op() -> None:
    check_no_cleaning("# Title\n\nA host paragraph.\n\n::: examples\ne1\n:::\n\nNext paragraph.\n")


def test_no_blank_line_inserted_between_list_item_and_fence() -> None:
    # Inserting a blank line here would risk ejecting the directive from the
    # list item's content scope.
    check_no_cleaning("# Title\n\n- a list item\n  ::: examples\n  e1\n  :::\n")


def test_no_blank_line_inserted_between_back_to_back_open_fences() -> None:
    # Back-to-back fence opens are already malformed; the cleaner deliberately
    # does not paper over the structure. The first fence is properly separated
    # so no other insertion fires either.
    check_no_cleaning("# Title\n\nA host paragraph.\n\n::: examples\n::: guidance\ne1\n:::\n")


def test_fence_shape_inside_code_block_does_not_trigger_blank_line() -> None:
    check_no_cleaning("# Title\n\nA paragraph.\n\n```\nA line\n::: examples\n```\n")


def test_open_fence_at_document_start_does_not_get_blank_line() -> None:
    # No prior content ⇒ nothing to separate from. (Resulting doc is an
    # orphan-annotation case the validator would reject, but this test is
    # specifically about the blank-line insertion guard.)
    check_no_cleaning("::: examples\ne1\n:::\n")


# ---------------------------------------------------------------------------
# Section 5 — AddSpaceAfterHeadingHashes
# ---------------------------------------------------------------------------


def test_missing_space_after_double_hash_is_inserted() -> None:
    input_md = "# Title\n\n##Subheading\n\nA paragraph.\n"
    expected_md = "# Title\n\n## Subheading\n\nA paragraph.\n"
    check_cleaning_from_md(
        input_markdown=input_md,
        expected_markdown=expected_md,
        expected_actions=[ExpectedAction(line_no=3, description_contains="missing space")],
    )


@pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
def test_missing_space_after_hashes_at_all_heading_levels(level: int) -> None:
    # We exercise the regex's `#{1,6}` quantifier across all six levels.
    # Output validation is opted out — building a properly-nested 6-level
    # doc just to test a regex bound would obscure the actual check.
    hashes = "#" * level
    input_md = f"{hashes}Heading text\n"
    expected_md = f"{hashes} Heading text\n"
    check_cleaning_from_md(
        input_markdown=input_md,
        expected_markdown=expected_md,
        expected_actions=[ExpectedAction(line_no=1, description_contains="missing space")],
        validate_output=False,
    )


def test_seven_hashes_is_left_alone() -> None:
    # `####### foo` is already accepted as a paragraph by the validator
    # (deliberate carve-out — see project_prompt_validation memo).
    check_no_cleaning("# Title\n\n####### not a heading\n\nA paragraph.\n")


def test_hashes_with_no_body_are_untouched() -> None:
    # `##` alone has no body — the regex requires at least one non-hash
    # non-whitespace char after the hashes. Adding a space would just produce
    # `## `, still an empty heading, so we correctly leave it for the
    # validator to report.
    check_no_cleaning("# Title\n\n##\n\nA paragraph.\n")


def test_heading_with_space_already_present_is_a_no_op() -> None:
    check_no_cleaning("# Title\n\n## Sub\n\nA paragraph.\n")


def test_heading_shape_inside_code_block_is_not_touched() -> None:
    check_no_cleaning("# Title\n\nA paragraph.\n\n```\n##NotAHeading\n```\n")


def test_hashes_not_at_line_start_are_not_touched() -> None:
    check_no_cleaning("# Title\n\nThis is text ##notAHeading and more.\n")


# ---------------------------------------------------------------------------
# Section 6 — Integration / pipeline
# ---------------------------------------------------------------------------


_NONTRIVIAL_CLEAN_DOC = (
    "# Title\n"
    "\n"
    "First host paragraph.\n"
    "\n"
    "::: examples\n"
    "an example\n"
    ":::\n"
    "\n"
    "Second host paragraph.\n"
    "\n"
    "::: guidance\n"
    "some guidance\n"
    ":::\n"
    "\n"
    "- list item 1\n"
    "- list item 2\n"
    "\n"
    "```python\n"
    "print('hi')\n"
    "```\n"
    "\n"
    "Final paragraph.\n"
)


def test_nontrivial_already_clean_doc_is_a_no_op() -> None:
    # Guards against over-firing: if any cleaner mutates a valid doc with
    # examples, guidance, lists, and code blocks, this test catches it.
    check_no_cleaning(_NONTRIVIAL_CLEAN_DOC)
    # Belt-and-braces: confirm the fixture itself actually validates.
    check_no_errors_from_md(_NONTRIVIAL_CLEAN_DOC)


def test_all_five_cleaners_fire_in_one_pass() -> None:
    # One input that exercises every cleaner: CRLF endings, missing space
    # after `:::`, indented fence open, missing blank line before fence, and
    # missing space after heading hashes.
    input_md = "# Title\r\n\r\n##Subheading\r\n\r\nA host paragraph.\r\n  :::examples\r\ne1\r\n:::\r\nFinal text.\r\n"
    expected_md = "# Title\n\n## Subheading\n\nA host paragraph.\n\n::: examples\ne1\n:::\n\nFinal text.\n"
    check_cleaning_from_md(
        input_markdown=input_md,
        expected_markdown=expected_md,
        expected_actions=[
            ExpectedAction(line_no=None, description_contains="line endings"),
            ExpectedAction(line_no=3, description_contains="missing space after `##`"),
            ExpectedAction(line_no=6, description_contains="missing space in"),
            ExpectedAction(line_no=6, description_contains="leading indent"),
            ExpectedAction(line_no=6, description_contains="blank line before"),
            ExpectedAction(line_no=8, description_contains="blank line after"),
        ],
    )


def test_cleaning_is_idempotent() -> None:
    # Re-cleaning a cleaned doc must produce the same text with no further
    # actions — otherwise the pipeline has a fixed-point bug and feeding it
    # its own output would oscillate.
    dirty = "# Title\r\n\r\n##Sub\r\n\r\nA host paragraph.\r\n  :::examples\r\ne1\r\n:::\r\nFinal text.\r\n"
    once = clean_prompt_from_string(dirty).cleaned_markup
    twice_result = clean_prompt_from_string(once)
    assert twice_result.cleaned_markup == once
    assert twice_result.actions_taken == []


def test_paragraph_directly_followed_by_indented_missing_space_fence() -> None:
    # Narrower than the all-five test — focuses on the
    # space → dedent → blank-line ordering interaction around a single fence.
    input_md = "# Title\n\nA host paragraph.\n  :::examples\ne1\n:::\n"
    expected_md = "# Title\n\nA host paragraph.\n\n::: examples\ne1\n:::\n"
    check_cleaning_from_md(
        input_markdown=input_md,
        expected_markdown=expected_md,
        expected_actions=[
            ExpectedAction(line_no=4, description_contains="missing space in"),
            ExpectedAction(line_no=4, description_contains="leading indent"),
            ExpectedAction(line_no=4, description_contains="blank line before"),
        ],
    )


# NOTE: "cleaning turns a failing doc into a passing one" was originally
# planned here. In practice the validator is lenient about every surface
# mistake the cleaner targets *except* a 4+ space indented fence inside a
# paragraph — and that case the cleaner deliberately refuses to fix (too
# ambiguous to repair correctly). The cleaner's value is heading off
# author mistakes that *look* wrong rather than unblocking validation, so
# the assertion can't actually fire on any honest input. Documenting the
# gap rather than writing a vacuous test.


def test_cleaning_does_not_introduce_validator_errors_of_unrelated_kinds() -> None:
    # Spot-check that none of the cleaners trip a heading-level-skip,
    # empty-heading, or orphan-annotation error as a side effect of the
    # transformations they apply.
    input_md = "# Title\n\nA host paragraph.\n:::examples\ne1\n:::\nNext paragraph.\n"
    cleaned = clean_prompt_from_string(input_md).cleaned_markup
    errors = find_errors_from_string(cleaned)
    forbidden = {
        PromptErrorType.HeadingLevelSkip,
        PromptErrorType.EmptyHeading,
        PromptErrorType.OrphanAnnotation,
    }
    triggered = {e.error_type for e in errors} & forbidden
    assert not triggered, f"cleaner introduced unexpected errors: {triggered}"
