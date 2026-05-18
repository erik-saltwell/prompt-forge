from __future__ import annotations

from ...._protocols.prompt_validator import MarkdownTokenList, PromptValidator
from ....model.prompt_validation_error import PromptError, PromptErrorType
from ._annotation_helpers import (
    find_matching_close,
    is_annotation_open,
)


class NoHeadingInAnnotation(PromptValidator):
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
                if inner.type == "heading_open":
                    line = (inner.map[0] + 1) if inner.map else 0
                    errors.append(
                        PromptError(
                            line=line,
                            error_type=PromptErrorType.HeadingInAnnotation,
                            error_message="Headings are not allowed inside an annotation.",
                        )
                    )
        return errors
