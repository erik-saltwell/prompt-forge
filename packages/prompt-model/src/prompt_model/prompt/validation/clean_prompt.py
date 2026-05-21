from __future__ import annotations

from ._cleaners import (
    AddBlankLineAroundFence,
    AddSpaceAfterFenceColons,
    AddSpaceAfterHeadingHashes,
    DedentTopLevelFence,
    NormalizeLineEndings,
)
from .cleaner_protocol import CleaningAction, CleaningResult, PromptCleaner


def _load_cleaners() -> list[PromptCleaner]:
    # Order matters: line endings first so the rest can assume LF; then make
    # the fence recognizable (add the missing space) before dedent and
    # blank-line insertion, both of which match on the well-formed fence shape.
    return [
        NormalizeLineEndings(),
        AddSpaceAfterFenceColons(),
        DedentTopLevelFence(),
        AddBlankLineAroundFence(),
        AddSpaceAfterHeadingHashes(),
    ]


def clean_prompt_from_string(input_markdown: str) -> CleaningResult:
    actions_taken: list[CleaningAction] = []
    cleaners: list[PromptCleaner] = _load_cleaners()
    current_prompt: str = input_markdown
    for cleaner in cleaners:
        cleaning_result: CleaningResult = cleaner.clean(current_prompt)
        current_prompt = cleaning_result.cleaned_markup
        actions_taken.extend(cleaning_result.actions_taken)

    return CleaningResult(cleaned_markup=current_prompt, actions_taken=actions_taken)
