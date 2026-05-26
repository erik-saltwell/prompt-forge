from __future__ import annotations

from ..._prompt import Document


class NoRedactionStrategy:
    """Returns ``None`` for every culprit — the renderer keeps every node verbatim.

    Useful for benchmarking against reference systems that show the actor the full
    prompt, and for debugging when you want to remove redaction as a variable.
    """

    def focus_ids(self, tree: Document, culprit_node_id: str) -> set[str] | None:
        return None
