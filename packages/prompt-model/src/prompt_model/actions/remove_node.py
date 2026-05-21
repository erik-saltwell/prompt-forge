from __future__ import annotations

from ..prompt import Document
from ._dry_run import validates_after
from ._walk import ChildContainer, children_of, find_node_by_id, find_parent_and_index
from .protocol import Action, ApplyContext, SkipReason
from .registry import register


class RemoveNodeAction:
    """Remove a node (and its subtree) from the tree.

    Targets a node by snapshot id. Cannot target the Document root or any
    annotation id — annotation removal goes through remove_example /
    remove_guidance."""

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id

    def _resolve(self, tree: Document) -> tuple[ChildContainer, int] | None:
        return find_parent_and_index(tree, self.node_id)

    def validate(self, tree: Document) -> SkipReason | None:
        located = self._resolve(tree)
        if located is None:
            # Distinguish "not in tree" from "id belongs to an annotation":
            # the latter would resolve under walk_all but never have a
            # structural parent.
            if find_node_by_id(tree, self.node_id) is not None:
                return SkipReason.TargetNotFound
            return SkipReason.TargetNotFound
        if not validates_after(tree, lambda t: self._do_remove(t)):
            return SkipReason.InvalidStructure
        return None

    def _do_remove(self, tree: Document) -> None:
        located = find_parent_and_index(tree, self.node_id)
        assert located is not None
        parent, index = located
        del children_of(parent)[index]

    def apply(self, tree: Document, ctx: ApplyContext | None = None) -> None:
        located = self._resolve(tree)
        assert located is not None, "apply() called without a successful validate()"
        parent, index = located
        children_of(parent).pop(index)


@register("delete_node")
def _build_delete_node(raw: dict) -> Action | SkipReason:
    node_id = raw.get("id")
    if not isinstance(node_id, str) or not node_id:
        return SkipReason.MissingRequired
    return RemoveNodeAction(node_id)
