from __future__ import annotations

from typing import Protocol

from markdown_it.token import Token

from ..validation_error import PromptError

type MarkdownToken = Token
type MarkdownTokenList = list[Token]


class PromptValidator(Protocol):
    def find_errors(self, tokens: MarkdownTokenList) -> list[PromptError]: ...
