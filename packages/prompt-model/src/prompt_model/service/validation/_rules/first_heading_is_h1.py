from __future__ import annotations

from markdown_it.token import Token

from ...._protocols.prompt_validator import MarkdownTokenList, PromptValidator
from ....model.prompt_validation_error import PromptError, PromptErrorType


class FirstHeadingIsH1(PromptValidator):
    def find_errors(self, tokens: MarkdownTokenList | None) -> list[PromptError]:
        if not tokens:
            return []

        for token in tokens:
            if token.type != "heading_open":
                continue

            level = _heading_level(token)
            if level is None:
                return []
            if level == 1:
                return []

            line = (token.map[0] + 1) if token.map else 0
            return [
                PromptError(
                    line=line,
                    error_type=PromptErrorType.FirstHeadingNotH1,
                    error_message=(f"First heading in the document must be h1; found h{level}."),
                )
            ]

        return []


def _heading_level(token: Token) -> int | None:
    tag = token.tag
    if not tag.startswith("h"):
        return None
    try:
        return int(tag[1:])
    except ValueError:
        return None
