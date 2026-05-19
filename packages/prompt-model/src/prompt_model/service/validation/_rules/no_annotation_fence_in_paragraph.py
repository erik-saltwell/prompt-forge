from __future__ import annotations

import re

from ...._protocols.prompt_validator import MarkdownTokenList, PromptValidator
from ....model.prompt_validation_error import PromptError, PromptErrorType

# Matches a recognized annotation fence (`::: examples`, `::: example`, or
# `::: guidance`) that appears at the start of a non-first line inside inline
# content — i.e. the author wrote what looks like a container open, but
# markdown-it-container did not recognize it (because the line is indented
# 4+ spaces, or otherwise glued into a paragraph). The leading `\n` is what
# distinguishes "fence-shaped line inside paragraph" from a same-line `:::`
# occurrence which is just inline prose.
_FENCE_INSIDE_PARAGRAPH = re.compile(r"\n[ \t]*:::[ \t]*(example|examples|guidance)\b")


class NoAnnotationFenceInParagraph(PromptValidator):
    def find_errors(self, tokens: MarkdownTokenList | None) -> list[PromptError]:
        if not tokens:
            return []

        errors: list[PromptError] = []
        for index, token in enumerate(tokens):
            if token.type != "paragraph_open":
                continue
            inline = tokens[index + 1] if index + 1 < len(tokens) else None
            if inline is None or inline.type != "inline":
                continue
            content: str = inline.content or ""
            start_line = (token.map[0] + 1) if token.map else 0
            for match in _FENCE_INSIDE_PARAGRAPH.finditer(content):
                newlines_before = content[: match.start()].count("\n")
                fence_line = start_line + newlines_before + 1
                kind = match.group(1)
                errors.append(
                    PromptError(
                        line=fence_line,
                        error_type=PromptErrorType.AnnotationFenceInParagraph,
                        error_message=(
                            f"`::: {kind}` appears inside a paragraph and was not recognized as an "
                            "annotation container; insert a blank line before it (and remove any "
                            "leading indentation)."
                        ),
                    )
                )
        return errors
