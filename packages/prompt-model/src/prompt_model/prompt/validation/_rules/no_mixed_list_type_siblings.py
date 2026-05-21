from __future__ import annotations

from ...validation_error import PromptError, PromptErrorType
from ..validator_protocol import MarkdownTokenList, PromptValidator

_CLOSE_TO_OPPOSITE_OPEN = {
    "bullet_list_close": "ordered_list_open",
    "ordered_list_close": "bullet_list_open",
}


class NoMixedListTypeSiblings(PromptValidator):
    def find_errors(self, tokens: MarkdownTokenList | None) -> list[PromptError]:
        if not tokens:
            return []

        errors: list[PromptError] = []

        for index, token in enumerate(tokens):
            opposite_open = _CLOSE_TO_OPPOSITE_OPEN.get(token.type)
            if opposite_open is None:
                continue
            if index + 1 >= len(tokens):
                continue
            next_token = tokens[index + 1]
            if next_token.type != opposite_open:
                continue

            line = (next_token.map[0] + 1) if next_token.map else 0
            errors.append(
                PromptError(
                    line=line,
                    error_type=PromptErrorType.MixedListTypeSiblings,
                    error_message=(
                        "Adjacent sibling lists of different kinds (ordered/unordered); "
                        "merge into one list or separate with intervening content."
                    ),
                )
            )

        return errors
