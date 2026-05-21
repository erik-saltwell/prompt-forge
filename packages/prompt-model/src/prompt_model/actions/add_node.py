from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .._utils import pydantic_aliases as py_types
from ..prompt import Document, List, ListItem, PromptNode
from ._dry_run import validates_after
from ._subtree import build_subtrees
from ._walk import ChildContainer, children_of, resolve_anchor
from .anchor import LocationAnchor
from .protocol import Action, ApplyContext, SkipReason
from .registry import register

_AnchorPosition = Literal["before", "after", "inside"]


class AddNodeAction:
    """Insert one or more nodes (with their full subtrees) at a location anchor.

    Payload forms:
    - `str` — markdown source; parsed via the standard `parse_from_string`
      pipeline. Multi-block markdown splats into multiple roots inserted at
      adjacent indices.
    - `dict` — full Pydantic node shape with `node_type` discriminator. May
      include inline `examples` / `guidance` groups on Paragraph and ListItem
      nodes. Yields a single root.

    Auto-wrap rules (symmetric with `move_node`):
    - Adjacent ListItem roots landing in a non-`List` parent are wrapped in
      a fresh unordered `List` (there is no source list to inherit `ordered`
      from, so we default to unordered).
    - A `List` root landing inside another `List` is unwrapped — its
      `ListItem` children splat into the destination list.
    - Any non-`ListItem` root landing in a `List` parent skips with
      `InvalidStructure`.
    """

    def __init__(self, subtree: object, anchor: LocationAnchor) -> None:
        self.subtree_raw = subtree
        self.anchor = anchor

    def _materialise(self) -> list[PromptNode] | None:
        return build_subtrees(self.subtree_raw)

    def validate(self, tree: Document) -> SkipReason | None:
        roots = self._materialise()
        if roots is None:
            return SkipReason.InvalidSubtree
        located = resolve_anchor(tree, self.anchor)
        if located is None:
            return SkipReason.InvalidAnchor
        parent, _ = located
        adapted = _adapt_roots(roots, parent)
        if adapted is None:
            return SkipReason.InvalidStructure

        def mutate(t: Document) -> None:
            self._do_insert(t, fresh=True)

        if not validates_after(tree, mutate):
            return SkipReason.InvalidStructure
        return None

    def _do_insert(self, tree: Document, *, fresh: bool) -> None:
        located = resolve_anchor(tree, self.anchor)
        assert located is not None
        parent, index = located
        roots = self._materialise()
        assert roots is not None
        adapted = _adapt_roots(roots, parent)
        assert adapted is not None
        # validates_after clones the tree, so when called via dry-run each
        # materialised node may be inserted into a clone. Deep-copy per root
        # so each dry-run sees an independent instance.
        if fresh:
            adapted = [n.model_copy(deep=True) for n in adapted]
        container = children_of(parent)
        for offset, node in enumerate(adapted):
            container.insert(index + offset, node)

    def apply(self, tree: Document, ctx: ApplyContext | None = None) -> None:
        self._do_insert(tree, fresh=False)


def _adapt_roots(roots: list[PromptNode], parent: ChildContainer) -> list[PromptNode] | None:
    """Apply auto-wrap / unwrap rules so `roots` are valid children of `parent`.

    Returns None when the combination is structurally impossible (a non-
    ListItem root targeted at a `List` parent)."""
    if isinstance(parent, List):
        out: list[PromptNode] = []
        for root in roots:
            if isinstance(root, ListItem):
                out.append(root)
            elif isinstance(root, List):
                out.extend(root.children)
            else:
                return None
        return out

    out = []
    run: list[ListItem] = []

    def flush() -> None:
        if run:
            out.append(List(ordered=False, children=list(run)))
            run.clear()

    for root in roots:
        if isinstance(root, ListItem):
            run.append(root)
        else:
            flush()
            out.append(root)
    flush()
    return out


@register("insert_node")
def _build_insert_node(raw: dict) -> Action | SkipReason:
    from .anchor import parse_anchor

    subtree = raw.get("subtree")
    if subtree is None:
        subtree = raw.get("node")  # accept either key
    if subtree is None:
        return SkipReason.MissingRequired
    anchor = parse_anchor(raw)
    if anchor is None:
        return SkipReason.MissingRequired
    return AddNodeAction(subtree, anchor)


class InsertNodeInput(BaseModel):
    """LLM-output schema for `insert_node`. Converts to AddNodeAction.

    `subtree` is markdown-only per the brainstorm decision — the Pydantic-dict
    escape hatch from prompt-actions.md is intentionally not exposed here.
    """

    action: Literal["insert_node"]
    target: py_types.NonBlankStr = Field(description="Hierarchical id of the anchor node to position relative to.")
    position: _AnchorPosition = Field(
        description="Placement relative to target: 'before'/'after' (sibling) or 'inside' (only child of an empty target)."
    )
    subtree: py_types.NonBlankStr = Field(
        description="Markdown source for the subtree to insert. Multi-block markdown splats into adjacent roots."
    )

    def to_action(self) -> Action:
        return AddNodeAction(self.subtree, LocationAnchor(target=self.target, position=self.position))
