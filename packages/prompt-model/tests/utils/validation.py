from __future__ import annotations

from prompt_model.prompt import PromptError, PromptErrorType
from prompt_model.prompt.validation import find_errors_from_string


def check_errors_from_md(markdown_text: str, expected_errors: list[PromptError]) -> None:
    actual_errors: list[PromptError] = find_errors_from_string(markdown_text)
    assert len(actual_errors) >= len(expected_errors)
    for excpected in expected_errors:
        assert excpected in actual_errors


def check_error_from_md(markdown_text: str, line: int, type: PromptErrorType) -> None:
    expected_errors: list[PromptError] = [PromptError(line=line, error_type=type, error_message=".")]
    check_errors_from_md(markdown_text, expected_errors)


def check_no_errors_from_md(markdown_text: str) -> None:
    check_errors_from_md(markdown_text, [])
