from __future__ import annotations

from ...._protocols.prompt_validator import MarkdownTokenList, PromptValidator
from ....model.prompt_validation_error import PromptError, PromptErrorType


class NoHeadingInListItem(PromptValidator):
    def find_errors(self, tokens: MarkdownTokenList | None) -> list[PromptError]:
        if not tokens:
            return []

        errors: list[PromptError] = []
        depth = 0

        for token in tokens:
            if token.type == "list_item_open":
                depth += 1
            elif token.type == "list_item_close":
                depth -= 1
            elif token.type == "heading_open" and depth > 0:
                line = (token.map[0] + 1) if token.map else 0
                errors.append(
                    PromptError(
                        line=line,
                        error_type=PromptErrorType.HeadingInListItem,
                        error_message=f"Heading {token.tag} is not allowed inside a list item.",
                    )
                )

        return errors
