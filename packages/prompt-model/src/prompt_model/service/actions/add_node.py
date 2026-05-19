from __future__ import annotations

from ..._protocols.action import Action, ApplyContext, SkipReason
from ...model import Document, PromptNode
from ._dry_run import validates_after
from ._subtree import build_subtree
from ._walk import ChildContainer, child_container, children_of, find_node_by_id, find_parent_and_index, walk_all
from .anchor import LocationAnchor
from .registry import register


def _resolve_anchor(tree: Document, anchor: LocationAnchor) -> tuple[ChildContainer, int] | None:
    """Map an anchor to (parent_container, insertion_index) over the parent's
    `children` list. Returns None if the target doesn't resolve or the
    parent isn't a container."""
    target = anchor.target
    if anchor.kind in ("first_child", "last_child"):
        parent: ChildContainer | None
        if isinstance(target, str):
            # Empty-string target is the Document root convention — Document
            # has no id, so this is the only way to address it as a parent.
            parent = tree if target == "" else child_container(find_node_by_id(tree, target))
        else:
            parent = child_container(target) if target in walk_all(tree) else None
        if parent is None:
            return None
        children = children_of(parent)
        return (parent, 0) if anchor.kind == "first_child" else (parent, len(children))

    located: tuple[ChildContainer, int] | None
    if isinstance(target, str):
        located = find_parent_and_index(tree, target)
    else:
        located = None
        for p in walk_all(tree):
            container = child_container(p)
            if container is None:
                continue
            for i, c in enumerate(children_of(container)):
                if c is target:
                    located = (container, i)
                    break
            if located is not None:
                break
    if located is None:
        return None
    parent, index = located
    return parent, index + (1 if anchor.kind == "after" else 0)


class AddNodeAction:
    """Insert a node (with its full subtree) into the tree at a location anchor.

    Payload forms:
    - `str` — shorthand: becomes a Paragraph with that text.
    - `dict` — full Pydantic node shape with `node_type` discriminator.
      May include inline `examples` / `guidance` groups on Paragraph and
      ListItem nodes.

    The inverse is a RemoveNodeAction targeting the freshly inserted node
    by synthetic id (minted at apply time) or by snapshot id (when this
    action was constructed as the undo of a RemoveNodeAction)."""

    def __init__(self, subtree: object, anchor: LocationAnchor) -> None:
        self.subtree_raw = subtree
        self.anchor = anchor
        # Set when constructed via `_for_undo` — carries the original
        # detached PromptNode so undo restores the exact object with its
        # snapshot ids, keeping anchors on other inverses stable under LIFO.
        self._captured: PromptNode | None = None

    @classmethod
    def _for_undo(cls, detached: PromptNode, anchor: LocationAnchor) -> AddNodeAction:
        action = cls(detached, anchor)
        action._captured = detached
        return action

    def _materialise(self) -> PromptNode | None:
        if self._captured is not None:
            return self._captured
        return build_subtree(self.subtree_raw)

    def validate(self, tree: Document) -> SkipReason | None:
        node = self._materialise()
        if node is None:
            return SkipReason.InvalidSubtree
        if _resolve_anchor(tree, self.anchor) is None:
            return SkipReason.InvalidAnchor

        def mutate(t: Document) -> None:
            self._do_insert(t, fresh=True)

        if not validates_after(tree, mutate):
            return SkipReason.InvalidStructure
        return None

    def _do_insert(self, tree: Document, *, fresh: bool) -> PromptNode:
        located = _resolve_anchor(tree, self.anchor)
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
        return node

    def apply(self, tree: Document, ctx: ApplyContext | None = None) -> Action:
        from .remove_node import RemoveNodeAction

        if ctx is None:
            ctx = ApplyContext.from_tree(tree)

        located = _resolve_anchor(tree, self.anchor)
        assert located is not None, "apply() called without a successful validate()"
        parent, index = located

        node = self._materialise()
        assert node is not None

        if self._captured is None:
            # Forward path: use the materialised node directly and stamp a
            # synthetic id so the returned RemoveNodeAction can address it.
            node.id = ctx.mint_inserted_node_id()
        # else: undo path — node already has its snapshot id.

        children_of(parent).insert(index, node)
        assert node.id is not None
        return RemoveNodeAction(node.id)


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
