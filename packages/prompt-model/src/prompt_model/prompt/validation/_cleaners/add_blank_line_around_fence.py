from __future__ import annotations

import re

from ..cleaner_protocol import CleaningAction, CleaningResult
from ._code_fence import in_code_block_flags

# Open fence: `::: examples` / `::: example` / `::: guidance`, optional leading
# whitespace, optional trailing content (case-insensitive on the word).
_OPEN_FENCE = re.compile(r"^[ \t]*:::[ \t]+(?:examples|example|guidance)\b", re.IGNORECASE)
# Close fence: a line that is exactly `:::` (with optional surrounding whitespace).
_CLOSE_FENCE = re.compile(r"^[ \t]*:::[ \t]*$")
# A line that begins a list item (unordered or ordered). When such a line
# directly precedes a fence we don't insert a blank line — doing so would risk
# ejecting the directive from the list item's content scope.
_LIST_ITEM = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+")


def _is_blank(line: str) -> bool:
    return line.strip() == ""


class AddBlankLineAroundFence:
    """Insert a blank line before an open annotation fence when the prior line
    is non-blank, and after a close fence when the following line is non-blank
    (and not itself a fence). Skipped when the adjacent line is itself an open
    fence — that case is already malformed and we don't want to paper over it."""

    def clean(self, markdown: str) -> CleaningResult:
        lines = markdown.split("\n")
        in_code = in_code_block_flags(lines)
        actions: list[CleaningAction] = []
        out: list[str] = []
        # Iterate with manual index because we need to peek behind into `out`
        # (which reflects already-emitted, possibly-modified content).
        for index, line in enumerate(lines):
            if not in_code[index] and _OPEN_FENCE.match(line):
                prev = out[-1] if out else None
                if prev is not None and not _is_blank(prev) and not _OPEN_FENCE.match(prev) and not _LIST_ITEM.match(prev):
                    out.append("")
                    actions.append(
                        CleaningAction(
                            description="Inserted blank line before `:::` annotation fence open.",
                            line_no=index + 1,
                        )
                    )
            out.append(line)
            if not in_code[index] and _CLOSE_FENCE.match(line):
                next_line = lines[index + 1] if index + 1 < len(lines) else None
                if next_line is not None and not _is_blank(next_line) and not _CLOSE_FENCE.match(next_line):
                    out.append("")
                    actions.append(
                        CleaningAction(
                            description="Inserted blank line after `:::` annotation fence close.",
                            line_no=index + 1,
                        )
                    )
        if not actions:
            return CleaningResult(cleaned_markup=markdown, actions_taken=[])
        return CleaningResult(cleaned_markup="\n".join(out), actions_taken=actions)
