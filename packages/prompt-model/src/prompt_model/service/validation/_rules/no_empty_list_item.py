from __future__ import annotations

from ...._protocols.prompt_validator import MarkdownTokenList, PromptValidator
from ....model.prompt_validation_error import PromptError, PromptErrorType


class NoEmptyListItem(PromptValidator):
    def find_errors(self, tokens: MarkdownTokenList | None) -> list[PromptError]:
        if not tokens:
            return []

        errors: list[PromptError] = []

        for index, token in enumerate(tokens):
            if token.type != "list_item_open":
                continue
            if not _is_empty_list_item(tokens, index):
                continue

            line = (token.map[0] + 1) if token.map else 0
            errors.append(
                PromptError(
                    line=line,
                    error_type=PromptErrorType.EmptyListItem,
                    error_message="List item has no text content.",
                )
            )

        return errors


def _is_empty_list_item(tokens: MarkdownTokenList, open_index: int) -> bool:
    next_index = open_index + 1
    if next_index >= len(tokens):
        return True

    next_token = tokens[next_index]
    if next_token.type == "list_item_close":
        return True

    if (
        next_token.type == "paragraph_open"
        and next_index + 2 < len(tokens)
        and tokens[next_index + 1].type == "inline"
        and tokens[next_index + 2].type == "paragraph_close"
        and not tokens[next_index + 1].content.strip()
    ):
        return True

    return False
