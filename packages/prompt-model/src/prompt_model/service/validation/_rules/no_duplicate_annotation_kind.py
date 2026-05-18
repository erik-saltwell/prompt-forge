from __future__ import annotations

from ...._protocols.prompt_validator import MarkdownTokenList, PromptValidator
from ....model.prompt_validation_error import PromptError, PromptErrorType
from ._annotation_helpers import (
    annotation_kind,
    annotation_name,
    find_matching_open,
    find_preceding_sibling_end,
    is_annotation_open,
    open_line,
)


class NoDuplicateAnnotationKind(PromptValidator):
    """At most one `::: examples` and one `::: guidance` per host."""

    def find_errors(self, tokens: MarkdownTokenList | None) -> list[PromptError]:
        if not tokens:
            return []

        errors: list[PromptError] = []
        for index, token in enumerate(tokens):
            if not is_annotation_open(token):
                continue
            kind = annotation_kind(token)
            cursor = index
            saw_same_kind = False
            while True:
                end_i = find_preceding_sibling_end(tokens, cursor)
                if end_i == -1:
                    break
                end_token = tokens[end_i]
                if end_token.nesting == -1 and annotation_name(end_token) is not None:
                    if annotation_kind(end_token) == kind:
                        saw_same_kind = True
                        break
                    open_i = find_matching_open(tokens, end_i)
                    if open_i == -1:
                        break
                    cursor = open_i
                    continue
                break  # hit a non-annotation sibling — host boundary
            if saw_same_kind:
                errors.append(
                    PromptError(
                        line=open_line(token),
                        error_type=PromptErrorType.DuplicateAnnotationKind,
                        error_message=f"Host already has a '::: {kind}' annotation; only one of each kind is allowed.",
                    )
                )
        return errors
