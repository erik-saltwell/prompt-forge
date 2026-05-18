from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ...model import PromptNode

type NodeRef = PromptNode
type NodeTarget = str | PromptNode

AnchorKind = Literal["after", "before", "first_child", "last_child"]

_ONE_KEY_TO_KIND: dict[str, AnchorKind] = {
    "after": "after",
    "before": "before",
    "first_child": "first_child",
    "last_child": "last_child",
}


class LocationAnchor(BaseModel):
    """Where to place a node, relative to an existing target.

    - `after` / `before` — sibling-relative; target is the sibling.
    - `first_child` / `last_child` — parent-relative; target is the parent.

    `target` is normally a snapshot ID (str) parsed from JSON. The executor
    may construct anchors with a direct node reference for undo entries
    pointing at nodes that didn't exist at snapshot time.
    """

    model_config = {"arbitrary_types_allowed": True}

    kind: AnchorKind
    target: NodeTarget


def parse_anchor(raw: dict) -> LocationAnchor | None:
    """Convert the JSON one-key form (e.g. `{"after": "2.1"}`) to a LocationAnchor.

    Returns None if `raw` is not a recognized anchor shape. Extra keys beyond
    the single anchor key are ignored, consistent with the lenient-parameter rule.
    """
    for key, kind in _ONE_KEY_TO_KIND.items():
        if key in raw:
            target = raw[key]
            if not isinstance(target, str) or not target:
                return None
            return LocationAnchor(kind=kind, target=target)
    return None
