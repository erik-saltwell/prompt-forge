from __future__ import annotations

from ...._protocols import CleaningAction, CleaningResult


class NormalizeLineEndings:
    """Convert CRLF (and lone CR) line endings to LF. Pure noise removal —
    every downstream rule assumes ``\\n``-separated lines."""

    def clean(self, markdown: str) -> CleaningResult:
        if "\r" not in markdown:
            return CleaningResult(cleaned_markup=markdown, actions_taken=[])
        cleaned = markdown.replace("\r\n", "\n").replace("\r", "\n")
        return CleaningResult(
            cleaned_markup=cleaned,
            actions_taken=[
                CleaningAction(
                    description="Normalized CRLF/CR line endings to LF.",
                    line_no=None,
                )
            ],
        )
