from __future__ import annotations

from ...._protocols.prompt_validator import MarkdownTokenList, PromptValidator
from ....model.prompt_validation_error import PromptError, PromptErrorType
from ._annotation_helpers import (
    annotation_kind,
    find_matching_close,
    is_annotation_open,
    open_line,
)


class NoEmptyAnnotation(PromptValidator):
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
            has_content = False
            for j in range(index + 1, close_index):
                inner = tokens[j]
                if inner.type == "inline" and inner.content.strip():
                    has_content = True
                    break
            if not has_content:
                errors.append(
                    PromptError(
                        line=open_line(token),
                        error_type=PromptErrorType.EmptyAnnotation,
                        error_message=f"Annotation '::: {annotation_kind(token)}' has no body content.",
                    )
                )
        return errors
