from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .._prompt import PromptNode

type NodeRef = PromptNode
type NodeTarget = str | PromptNode

AnchorKind = Literal["before", "after", "inside"]

_VALID_POSITIONS: frozenset[str] = frozenset(("before", "after", "inside"))


class LocationAnchor(BaseModel):
    """Where to place a node, relative to an existing target.

    - `before` / `after` — sibling-relative; target is the sibling.
    - `inside` — parent-relative; target is the parent. Only valid when the
      target has no existing children (empty Section, empty ListItem, or
      annotation host with no group of the relevant kind).

    `target` is normally a snapshot ID (str) parsed from JSON. The executor
    may also construct anchors with a direct `PromptNode` reference when the
    target is known in-process.
    """

    model_config = {"arbitrary_types_allowed": True}

    position: AnchorKind
    target: NodeTarget


def parse_anchor(raw: dict) -> LocationAnchor | None:
    """Read flat `target` + `position` fields off an action dict and build
    a LocationAnchor. Returns None if either field is missing, the position
    is not one of the three valid values, or the target is not a non-empty
    string."""
    target = raw.get("target")
    position = raw.get("position")
    if not isinstance(target, str) or not target:
        return None
    if position not in _VALID_POSITIONS:
        return None
    return LocationAnchor(position=position, target=target)
