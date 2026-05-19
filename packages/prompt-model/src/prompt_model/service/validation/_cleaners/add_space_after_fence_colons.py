from __future__ import annotations

import re

from ...._protocols import CleaningAction, CleaningResult
from ._code_fence import in_code_block_flags

# `:::examples` / `:::example` / `:::guidance` at the start of a line
# (optional leading whitespace), with no space between the colons and the word.
# Case-insensitive on the word, but the author's casing is preserved in the
# replacement — we only insert the missing space.
_MISSING_SPACE = re.compile(r"^([ \t]*):::((?i:examples|example|guidance))\b")


class AddSpaceAfterFenceColons:
    """``:::examples`` → ``::: examples`` (and the same for ``:::example`` /
    ``:::guidance``). Only at line start, only outside fenced code blocks."""

    def clean(self, markdown: str) -> CleaningResult:
        lines = markdown.split("\n")
        in_code = in_code_block_flags(lines)
        actions: list[CleaningAction] = []
        for index, line in enumerate(lines):
            if in_code[index]:
                continue
            match = _MISSING_SPACE.match(line)
            if match is None:
                continue
            lines[index] = f"{match.group(1)}::: {match.group(2)}{line[match.end() :]}"
            actions.append(
                CleaningAction(
                    description=f"Inserted missing space in `:::{match.group(2)}` fence open.",
                    line_no=index + 1,
                )
            )
        if not actions:
            return CleaningResult(cleaned_markup=markdown, actions_taken=[])
        return CleaningResult(cleaned_markup="\n".join(lines), actions_taken=actions)
