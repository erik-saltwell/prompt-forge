from __future__ import annotations

import re

from ...._protocols import CleaningAction, CleaningResult
from ._code_fence import in_code_block_flags

# 1–3 leading spaces followed by an annotation fence open. 4+ spaces is left
# alone — at that indent we can't safely tell intentional list-nesting from
# accidental indent, and the validator will flag it via NoAnnotationFenceInParagraph.
_INDENTED_FENCE = re.compile(r"^( {1,3}):::[ \t]+(?:examples|example|guidance)\b", re.IGNORECASE)
# A line that begins a list item (unordered or ordered).
_LIST_ITEM = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+")


class DedentTopLevelFence:
    """Strip 1–3 spaces of leading indent from a line that is unambiguously an
    annotation fence open, but only when the prior non-blank line is not a
    list item (where the indent would be carrying semantic meaning)."""

    def clean(self, markdown: str) -> CleaningResult:
        lines = markdown.split("\n")
        in_code = in_code_block_flags(lines)
        actions: list[CleaningAction] = []
        for index, line in enumerate(lines):
            if in_code[index] or not _INDENTED_FENCE.match(line):
                continue
            if self._prior_non_blank_is_list_item(lines, in_code, index):
                continue
            lines[index] = line.lstrip(" ")
            actions.append(
                CleaningAction(
                    description="Removed leading indent from `:::` annotation fence open at top level.",
                    line_no=index + 1,
                )
            )
        if not actions:
            return CleaningResult(cleaned_markup=markdown, actions_taken=[])
        return CleaningResult(cleaned_markup="\n".join(lines), actions_taken=actions)

    @staticmethod
    def _prior_non_blank_is_list_item(lines: list[str], in_code: list[bool], index: int) -> bool:
        for back in range(index - 1, -1, -1):
            if in_code[back]:
                return True  # be conservative if previous context is code
            if lines[back].strip() == "":
                continue
            return _LIST_ITEM.match(lines[back]) is not None
        return False
