from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class CleaningAction:
    description: str
    line_no: int | None


@dataclass
class CleaningResult:
    cleaned_markup: str
    actions_taken: list[CleaningAction]


class PromptCleaner(Protocol):
    def clean(self, markdown: str) -> CleaningResult: ...
