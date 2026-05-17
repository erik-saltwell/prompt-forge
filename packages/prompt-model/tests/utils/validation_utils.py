from __future__ import annotations

from pathlib import Path

from prompt_model.model import PromptError, PromptErrorType
from prompt_model.service.validation import find_errors_from_file, find_errors_from_string


def check_errors(expected_errors: list[PromptError], actual_errors: list[PromptError]) -> None:
    assert len(actual_errors) >= len(expected_errors)
    for excpected in expected_errors:
        assert excpected in actual_errors


def assert_validation_from_file(test_file: Path, expected_errors: list[PromptError]) -> None:
    actual_errors: list[PromptError] = find_errors_from_file(test_file)
    check_errors(expected_errors, actual_errors)


def assert_validation_from_string(markdown_text: str, expected_errors: list[PromptError]) -> None:
    actual_errors: list[PromptError] = find_errors_from_string(markdown_text)
    check_errors(expected_errors, actual_errors)


def assert_single_error_from_file(test_file: Path, line: int, type: PromptErrorType) -> None:
    expected_errors: list[PromptError] = [PromptError(line=line, error_type=type, error_message=".")]
    assert_validation_from_file(test_file, expected_errors)


def assert_single_error_from_string(markdown_text: str, line: int, type: PromptErrorType) -> None:
    expected_errors: list[PromptError] = [PromptError(line=line, error_type=type, error_message=".")]
    assert_validation_from_string(markdown_text, expected_errors)
