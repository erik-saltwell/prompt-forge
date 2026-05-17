from __future__ import annotations

from typing import Any, Protocol

from ..model.prompt_validation_error import PromptError

type MarkdownToken = dict[str, Any]
type MarkdownTokenList = list[MarkdownToken]


class PromptValidator(Protocol):
    def find_errors(self, tokens: MarkdownTokenList) -> list[PromptError]: ...
