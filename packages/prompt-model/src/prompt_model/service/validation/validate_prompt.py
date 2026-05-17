from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt

from ..._protocols.prompt_validator import MarkdownTokenList, PromptValidator
from ...model.prompt_validation_error import PromptError
from ._rules.first_heading_is_h1 import FirstHeadingIsH1
from ._rules.markdown_not_empty import MarkdownNotEmpty
from ._rules.no_heading_level_skip import NoHeadingLevelSkip

_PARSER = MarkdownIt("commonmark").enable("table")


def _load_validators() -> list[PromptValidator]:
    return [MarkdownNotEmpty(), FirstHeadingIsH1(), NoHeadingLevelSkip()]


def _load_tokens(markdown_text: str) -> MarkdownTokenList:
    return _PARSER.parse(markdown_text)


def find_errors_from_file(filepath: Path) -> list[PromptError]:
    if not filepath.exists():
        raise FileNotFoundError(filepath)
    if not filepath.is_file():
        raise IsADirectoryError(filepath)
    markdown_text: str = filepath.read_text()
    return find_errors_from_string(markdown_text)


def find_errors_from_string(markdown_text: str) -> list[PromptError]:
    results: list[PromptError] = []
    validators: list[PromptValidator] = _load_validators()
    tokens: MarkdownTokenList = _load_tokens(markdown_text)
    for validator in validators:
        results.extend(validator.find_errors(tokens))

    return results
