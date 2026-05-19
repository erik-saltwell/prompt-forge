from __future__ import annotations

import re

# Matches an opening or closing ``` or ~~~ code fence (with optional info string
# for opens). We only need to toggle in/out of a fenced code block — we do not
# attempt to model indented code blocks, since none of the cleaners would
# legitimately edit a 4-space-indented line anyway.
_FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")


def in_code_block_flags(lines: list[str]) -> list[bool]:
    """Return a list parallel to ``lines`` indicating whether each line sits
    inside a fenced code block. The fence line itself is reported as inside
    (so cleaners skip it too)."""
    flags: list[bool] = []
    inside = False
    open_marker: str | None = None
    for line in lines:
        match = _FENCE_RE.match(line)
        if match is None:
            flags.append(inside)
            continue
        marker = match.group(1)[0] * 3  # normalize to 3-char marker type
        if not inside:
            inside = True
            open_marker = marker
            flags.append(True)
        elif open_marker is not None and match.group(1)[0] * 3 == open_marker:
            flags.append(True)
            inside = False
            open_marker = None
        else:
            flags.append(inside)
    return flags
