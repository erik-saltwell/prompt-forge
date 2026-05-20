from __future__ import annotations

from ..._protocols.action import Action, ApplyContext, SkipReason
from ...model import Document, PromptNode
from ._dry_run import validates_after
from ._subtree import build_subtree
from ._walk import children_of, resolve_anchor
from .anchor import LocationAnchor
from .registry import register


class AddNodeAction:
    """Insert a node (with its full subtree) into the tree at a location anchor.

    Payload forms:
    - `str` — shorthand: becomes a Paragraph with that text.
    - `dict` — full Pydantic node shape with `node_type` discriminator.
      May include inline `examples` / `guidance` groups on Paragraph and
      ListItem nodes."""

    def __init__(self, subtree: object, anchor: LocationAnchor) -> None:
        self.subtree_raw = subtree
        self.anchor = anchor

    def _materialise(self) -> PromptNode | None:
        return build_subtree(self.subtree_raw)

    def validate(self, tree: Document) -> SkipReason | None:
        node = self._materialise()
        if node is None:
            return SkipReason.InvalidSubtree
        if resolve_anchor(tree, self.anchor) is None:
            return SkipReason.InvalidAnchor

        def mutate(t: Document) -> None:
            self._do_insert(t, fresh=True)

        if not validates_after(tree, mutate):
            return SkipReason.InvalidStructure
        return None

    def _do_insert(self, tree: Document, *, fresh: bool) -> None:
        located = resolve_anchor(tree, self.anchor)
        assert located is not None
        parent, index = located
        node = self._materialise()
        assert node is not None
        if fresh:
            # validates_after clones the tree, so this `node` may be inserted
            # into a clone. Deep-copy the materialised subtree so each
            # dry-run sees an independent instance.
            node = node.model_copy(deep=True)
        children_of(parent).insert(index, node)

    def apply(self, tree: Document, ctx: ApplyContext | None = None) -> None:
        self._do_insert(tree, fresh=False)


@register("insert_node")
def _build_insert_node(raw: dict) -> Action | SkipReason:
    from .anchor import parse_anchor

    subtree = raw.get("subtree")
    if subtree is None:
        subtree = raw.get("node")  # accept either key
    if subtree is None:
        return SkipReason.MissingRequired
    anchor_raw = raw.get("anchor")
    if not isinstance(anchor_raw, dict):
        return SkipReason.MissingRequired
    anchor = parse_anchor(anchor_raw)
    if anchor is None:
        return SkipReason.MissingRequired
    return AddNodeAction(subtree, anchor)
