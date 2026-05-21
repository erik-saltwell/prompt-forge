from __future__ import annotations

from markdown_it.token import Token

from ...validation_error import PromptError, PromptErrorType
from ..validator_protocol import MarkdownTokenList, PromptValidator


class NoHeadingLevelSkip(PromptValidator):
    def find_errors(self, tokens: MarkdownTokenList | None) -> list[PromptError]:
        if not tokens:
            return []

        errors: list[PromptError] = []
        open_levels: list[int] = []

        for token in tokens:
            if token.type != "heading_open":
                continue

            level = _heading_level(token)
            if level is None:
                continue

            line = (token.map[0] + 1) if token.map else 0

            while open_levels and open_levels[-1] >= level:
                open_levels.pop()

            if open_levels:
                max_allowed = open_levels[-1] + 1
                if level > max_allowed:
                    errors.append(
                        PromptError(
                            line=line,
                            error_type=PromptErrorType.HeadingLevelSkip,
                            error_message=(
                                f"Heading level skip: jumped from h{open_levels[-1]} to h{level}; expected at most h{max_allowed}."
                            ),
                        )
                    )

            open_levels.append(level)

        return errors


def _heading_level(token: Token) -> int | None:
    tag = token.tag
    if not tag.startswith("h"):
        return None
    try:
        return int(tag[1:])
    except ValueError:
        return None
