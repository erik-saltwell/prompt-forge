from __future__ import annotations

from ...validation_error import PromptError, PromptErrorType
from ..validator_protocol import MarkdownTokenList, PromptValidator


class NoEmptyHeading(PromptValidator):
    def find_errors(self, tokens: MarkdownTokenList | None) -> list[PromptError]:
        if not tokens:
            return []

        errors: list[PromptError] = []

        for index, token in enumerate(tokens):
            if token.type != "heading_open":
                continue

            next_token = tokens[index + 1] if index + 1 < len(tokens) else None
            text = next_token.content if next_token and next_token.type == "inline" else ""
            if text.strip():
                continue

            line = (token.map[0] + 1) if token.map else 0
            errors.append(
                PromptError(
                    line=line,
                    error_type=PromptErrorType.EmptyHeading,
                    error_message=f"Heading {token.tag} has no text content.",
                )
            )

        return errors
