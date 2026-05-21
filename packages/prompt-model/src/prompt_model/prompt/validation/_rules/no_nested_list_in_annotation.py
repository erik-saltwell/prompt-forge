from __future__ import annotations

from ...validation_error import PromptError, PromptErrorType
from ..validator_protocol import MarkdownTokenList, PromptValidator
from ._annotation_helpers import (
    find_matching_close,
    is_annotation_open,
)


class NoNestedListInAnnotation(PromptValidator):
    """When an annotation directive uses the list form, each list item's
    content must be a single paragraph (possibly multi-line via softbreaks).
    A nested list inside an item is rejected.
    """

    def find_errors(self, tokens: MarkdownTokenList | None) -> list[PromptError]:
        if not tokens:
            return []

        errors: list[PromptError] = []
        for i, token in enumerate(tokens):
            if not is_annotation_open(token):
                continue
            close_i = find_matching_close(tokens, i)
            if close_i == -1:
                continue
            outer_list_level = tokens[i].level + 1
            # The outer bullet list's items are at outer_list_level + 1.
            # A nested list inside an item is at level >= outer_list_level + 2.
            inside_outer_list = False
            outer_list_close_i = -1
            for j in range(i + 1, close_i):
                t = tokens[j]
                if not inside_outer_list:
                    if t.type == "bullet_list_open" and t.level == outer_list_level:
                        inside_outer_list = True
                        outer_list_close_i = find_matching_close(tokens, j)
                    continue
                if j >= outer_list_close_i:
                    inside_outer_list = False
                    continue
                if t.type in ("bullet_list_open", "ordered_list_open") and t.level >= outer_list_level + 2:
                    line = (t.map[0] + 1) if t.map else 0
                    errors.append(
                        PromptError(
                            line=line,
                            error_type=PromptErrorType.NestedListInAnnotation,
                            error_message="Nested lists are not allowed inside an annotation list item.",
                        )
                    )
        return errors
