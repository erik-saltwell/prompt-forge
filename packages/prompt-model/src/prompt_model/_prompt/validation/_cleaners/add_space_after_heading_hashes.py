from __future__ import annotations

import re

from ..cleaner_protocol import CleaningAction, CleaningResult
from ._code_fence import in_code_block_flags

# 1–6 `#` immediately followed by a non-`#`, non-space character. Without the
# space, mistune treats the line as a paragraph rather than a heading.
_MISSING_SPACE_HEADING = re.compile(r"^(#{1,6})([^#\s].*)$")


class AddSpaceAfterHeadingHashes:
    """``##Foo`` → ``## Foo``. Only outside fenced code blocks."""

    def clean(self, markdown: str) -> CleaningResult:
        lines = markdown.split("\n")
        in_code = in_code_block_flags(lines)
        actions: list[CleaningAction] = []
        for index, line in enumerate(lines):
            if in_code[index]:
                continue
            match = _MISSING_SPACE_HEADING.match(line)
            if match is None:
                continue
            hashes = match.group(1)
            lines[index] = f"{hashes} {match.group(2)}"
            actions.append(
                CleaningAction(
                    description=f"Inserted missing space after `{hashes}` heading marker.",
                    line_no=index + 1,
                )
            )
        if not actions:
            return CleaningResult(cleaned_markup=markdown, actions_taken=[])
        return CleaningResult(cleaned_markup="\n".join(lines), actions_taken=actions)
