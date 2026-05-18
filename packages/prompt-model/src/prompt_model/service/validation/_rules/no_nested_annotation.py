from __future__ import annotations

from ...._protocols.prompt_validator import MarkdownTokenList, PromptValidator
from ....model.prompt_validation_error import PromptError, PromptErrorType
from ._annotation_helpers import (
    find_matching_close,
    is_annotation_open,
    open_line,
)


class NoNestedAnnotation(PromptValidator):
    def find_errors(self, tokens: MarkdownTokenList | None) -> list[PromptError]:
        if not tokens:
            return []

        errors: list[PromptError] = []
        for index, token in enumerate(tokens):
            if not is_annotation_open(token):
                continue
            close_index = find_matching_close(tokens, index)
            if close_index == -1:
                continue
            for j in range(index + 1, close_index):
                inner = tokens[j]
                if is_annotation_open(inner):
                    errors.append(
                        PromptError(
                            line=open_line(inner),
                            error_type=PromptErrorType.NestedAnnotation,
                            error_message="Annotations cannot be nested inside other annotations.",
                        )
                    )
        return errors
