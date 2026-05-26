from __future__ import annotations

from typing import Protocol

from ..._prompt import Document


class RedactionStrategy(Protocol):
    """Given a tree and a culprit node id, returns the set of node ids whose
    content the renderer should keep verbatim. `None` means keep everything.
    """

    def focus_ids(self, tree: Document, culprit_node_id: str) -> set[str] | None: ...
