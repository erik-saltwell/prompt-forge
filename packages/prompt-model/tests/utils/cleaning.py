from __future__ import annotations

from dataclasses import dataclass

from prompt_model._protocols import CleaningAction, CleaningResult
from prompt_model.service.validation.clean_prompt import clean_prompt_from_string

from .validation import check_no_errors_from_md


@dataclass(frozen=True)
class ExpectedAction:
    """A loose specification for an action we expect to see in the result.

    ``line_no`` must match exactly (use ``None`` for whole-document actions
    like CRLF normalization). ``description_contains`` is a substring check so
    tests don't break when we tweak action wording — assert on the meaningful
    keyword (e.g. ``"blank line before"``)."""

    line_no: int | None
    description_contains: str


def check_cleaning_from_md(
    input_markdown: str,
    expected_markdown: str,
    expected_actions: list[ExpectedAction],
    validate_output: bool = True,
) -> None:
    """Run the cleaner pipeline on ``input_markdown`` and assert both the
    final output and the reported actions match. ``expected_actions`` is
    treated as a subset — extra actions are allowed (mirrors the validator
    helper's ``check_errors_from_md`` semantics).

    By default, the cleaned markup is also asserted to pass ``prompt_validator``
    — the whole point of cleaning is to produce valid markup. Pass
    ``validate_output=False`` for tests that intentionally exercise inputs the
    cleaner can only partially repair."""
    result: CleaningResult = clean_prompt_from_string(input_markdown)
    assert result.cleaned_markup == expected_markdown, (
        f"Cleaned markup did not match expected.\n--- expected ---\n{expected_markdown!r}\n--- actual ---\n{result.cleaned_markup!r}"
    )
    _assert_actions_reported(result.actions_taken, expected_actions)
    if validate_output:
        check_no_errors_from_md(result.cleaned_markup)


def check_cleaned_output(
    input_markdown: str,
    expected_markdown: str,
    validate_output: bool = True,
) -> None:
    """Assert the cleaner produces ``expected_markdown``, without caring which
    actions were reported. Also asserts the cleaned output passes the
    validator unless ``validate_output=False``."""
    result: CleaningResult = clean_prompt_from_string(input_markdown)
    assert result.cleaned_markup == expected_markdown, f"--- expected ---\n{expected_markdown!r}\n--- actual ---\n{result.cleaned_markup!r}"
    if validate_output:
        check_no_errors_from_md(result.cleaned_markup)


def check_action_reported(
    input_markdown: str,
    line_no: int | None,
    description_contains: str,
) -> None:
    """Assert that at least one reported action matches the given line and
    description substring. Useful for single-rule unit tests."""
    result: CleaningResult = clean_prompt_from_string(input_markdown)
    _assert_actions_reported(
        result.actions_taken,
        [ExpectedAction(line_no=line_no, description_contains=description_contains)],
    )


def check_no_cleaning(input_markdown: str) -> None:
    """Assert the cleaner is a no-op: output equals input and no actions are
    reported. Use for already-clean inputs and for inputs we deliberately
    refuse to touch (e.g. fence-shaped content inside a code block)."""
    result: CleaningResult = clean_prompt_from_string(input_markdown)
    assert result.cleaned_markup == input_markdown, (
        f"Expected no changes but markup was modified.\n--- input ---\n{input_markdown!r}\n--- actual ---\n{result.cleaned_markup!r}"
    )
    assert result.actions_taken == [], f"Expected no actions but got: {[(a.line_no, a.description) for a in result.actions_taken]}"


def _assert_actions_reported(
    actual: list[CleaningAction],
    expected: list[ExpectedAction],
) -> None:
    for spec in expected:
        matches = [a for a in actual if a.line_no == spec.line_no and spec.description_contains in a.description]
        assert matches, (
            f"No reported action matched line={spec.line_no!r} "
            f"containing {spec.description_contains!r}. "
            f"Actual actions: {[(a.line_no, a.description) for a in actual]}"
        )
