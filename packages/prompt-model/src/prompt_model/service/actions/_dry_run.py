from __future__ import annotations

from collections.abc import Callable

from ...model import Document


def validates_after(tree: Document, mutate: Callable[[Document], None]) -> bool:
    """Return True if applying `mutate` to a clone of `tree` produces a
    document whose rendered markdown passes validate-prompt.

    Used by structural actions (insert_node / delete_node) to decide
    whether a mutation should be skipped — we lean on the existing
    validator rather than re-encoding structural rules per action."""
    from ..validation import find_errors_from_string

    clone = tree.model_copy(deep=True)
    try:
        mutate(clone)
        md = clone.to_markdown()
    except Exception:
        return False
    if not md.strip():
        return False
    return not find_errors_from_string(md)
