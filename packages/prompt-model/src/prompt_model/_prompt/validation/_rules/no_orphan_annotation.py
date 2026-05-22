from __future__ import annotations

from ...validation_error import PromptError, PromptErrorType
from ..validator_protocol import MarkdownTokenList, PromptValidator
from ._annotation_helpers import (
    find_preceding_non_annotation_sibling_end,
    is_annotation_open,
    open_line,
    sibling_block_type,
)


class NoOrphanAnnotation(PromptValidator):
    def find_errors(self, tokens: MarkdownTokenList | None) -> list[PromptError]:
        if not tokens:
            return []

        errors: list[PromptError] = []
        for index, token in enumerate(tokens):
            if not is_annotation_open(token):
                continue
            end_i = find_preceding_non_annotation_sibling_end(tokens, index)
            is_orphan = end_i == -1 or sibling_block_type(tokens[end_i]) == "heading"
            if is_orphan:
                errors.append(
                    PromptError(
                        line=open_line(token),
                        error_type=PromptErrorType.OrphanAnnotation,
                        error_message="Annotation has no preceding paragraph or list item to attach to.",
                    )
                )
        return errors
