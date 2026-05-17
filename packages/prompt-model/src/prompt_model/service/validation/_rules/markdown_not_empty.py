from __future__ import annotations

from ...._protocols.prompt_validator import MarkdownTokenList, PromptValidator
from ....model.prompt_validation_error import PromptError, PromptErrorType


class MarkdownNotEmpty(PromptValidator):
    def find_errors(self, tokens: MarkdownTokenList | None) -> list[PromptError]:
        if tokens and not all(token.get("type") == "blank_line" for token in tokens):
            return []

        return [
            PromptError(
                line=0,
                error_type=PromptErrorType.EmptyFile,
                error_message="Markdown must not be empty.",
            )
        ]
