from __future__ import annotations

from typing import Final

from ...._protocols.prompt_validator import MarkdownTokenList, PromptValidator
from ....model.prompt_validation_error import PromptError, PromptErrorType
from ._annotation_helpers import (
    find_preceding_non_annotation_sibling_end,
    is_annotation_open,
    open_line,
    sibling_block_type,
)

_LEGAL_HOST_TYPES: Final[frozenset[str]] = frozenset({"paragraph", "list_item"})


class AnnotationHostIsValid(PromptValidator):
    def find_errors(self, tokens: MarkdownTokenList | None) -> list[PromptError]:
        if not tokens:
            return []

        errors: list[PromptError] = []
        for index, token in enumerate(tokens):
            if not is_annotation_open(token):
                continue
            end_i = find_preceding_non_annotation_sibling_end(tokens, index)
            if end_i == -1:
                continue  # orphan — covered by NoOrphanAnnotation
            sib_type = sibling_block_type(tokens[end_i])
            if sib_type == "heading":
                continue  # orphan — covered by NoOrphanAnnotation
            if sib_type in _LEGAL_HOST_TYPES:
                continue
            errors.append(
                PromptError(
                    line=open_line(token),
                    error_type=PromptErrorType.IllegalAnnotationHost,
                    error_message=f"Annotation cannot attach to a '{sib_type}'; only paragraphs and list items are valid hosts.",
                )
            )
        return errors
