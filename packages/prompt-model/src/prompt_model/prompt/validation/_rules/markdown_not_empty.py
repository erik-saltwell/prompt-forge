from __future__ import annotations

from ...validation_error import PromptError, PromptErrorType
from ..validator_protocol import MarkdownTokenList, PromptValidator


class MarkdownNotEmpty(PromptValidator):
    def find_errors(self, tokens: MarkdownTokenList | None) -> list[PromptError]:
        if tokens:
            return []

        return [
            PromptError(
                line=0,
                error_type=PromptErrorType.EmptyFile,
                error_message="Markdown must not be empty.",
            )
        ]
