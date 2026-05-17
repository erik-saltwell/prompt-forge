from pathlib import Path

import pytest
from prompt_model.model.prompt_validation_error import PromptErrorType
from prompt_model.service.validation.validate_prompt import find_errors_from_file

from .utils.validation_utils import assert_single_error_from_string

skipped_hierarchy_1: str = """# First Level
test test test

### Second Level"""

start_at_h2: str = """## First Level
test test test

### Second Level"""

empty_header: str = """# First
test test test
#
test test test"""


def test_find_errors_raises_file_not_found_error_when_filepath_does_not_exist(tmp_path: Path) -> None:
    filepath = tmp_path / "missing.md"

    with pytest.raises(FileNotFoundError):
        find_errors_from_file(filepath)


def test_find_errors_raises_is_a_directory_error_when_filepath_is_not_a_file(tmp_path: Path) -> None:
    with pytest.raises(IsADirectoryError):
        find_errors_from_file(tmp_path)


def test_empty_file() -> None:
    assert_single_error_from_string("", 0, PromptErrorType.EmptyFile)


def test_skipped_hierarchy() -> None:
    assert_single_error_from_string(skipped_hierarchy_1, 4, PromptErrorType.HeadingLevelSkip)


def test_first_header_is_h1() -> None:
    assert_single_error_from_string(start_at_h2, 1, PromptErrorType.FirstHeadingNotH1)


def test_empty_header() -> None:
    assert_single_error_from_string(empty_header, 3, PromptErrorType.EmptyHeading)
