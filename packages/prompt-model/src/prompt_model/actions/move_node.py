from __future__ import annotations

from ..prompt import Document, List, ListItem, PromptNode, Section
from ._dry_run import validates_after
from ._walk import (
    ChildContainer,
    children_of,
    find_parent_and_index,
    find_parent_of_node,
    is_descendant,
    resolve_anchor,
    section_level_for_parent,
    walk_all,
)
from .anchor import LocationAnchor, parse_anchor
from .protocol import Action, ApplyContext, SkipReason
from .registry import register


class MoveNodeAction:
    """Relocate a node (with its full subtree) to a new location anchor.

    Node-only in v1 — targeting an annotation id skips. The subtree, including
    any `examples` / `guidance` groups on host nodes, moves as one unit.

    Three side-effects beyond the basic lift-and-insert:
    - **Auto-wrap.** A `ListItem` landing in a non-`List` parent is wrapped
      in a fresh `List` inheriting the source list's `ordered` flag.
    - **Section level shift.** A `Section` moved to a different section depth
      has its `level` (and all nested `Section.level`s) shifted by the delta
      so the resulting tree still validates. Skipped if any resulting level
      would exceed 6.
    - **Source-list cleanup.** If lifting the node empties its source `List`,
      that list is also removed (empty Lists can't be reserialised).

    """

    def __init__(self, node_id: str, anchor: LocationAnchor) -> None:
        self.node_id = node_id
        self.anchor = anchor

    def validate(self, tree: Document) -> SkipReason | None:
        source = find_parent_and_index(tree, self.node_id)
        if source is None:
            # ID may belong to an annotation or be absent entirely; both skip.
            return SkipReason.TargetNotFound
        source_parent, source_index = source
        node = children_of(source_parent)[source_index]

        dest = resolve_anchor(tree, self.anchor)
        if dest is None:
            return SkipReason.InvalidAnchor
        dest_parent, dest_index = dest

        if is_descendant(dest_parent, node):
            return SkipReason.InvalidAnchor

        if self._is_noop(source_parent, source_index, dest_parent, dest_index):
            return SkipReason.InvalidAnchor

        if isinstance(node, Section):
            new_top_level = section_level_for_parent(tree, dest_parent)
            if new_top_level is None:
                return SkipReason.InvalidStructure
            delta = new_top_level - node.level
            for d in walk_all(node):
                if isinstance(d, Section) and not 1 <= d.level + delta <= 6:
                    return SkipReason.InvalidStructure

        def mutate(clone: Document) -> None:
            self._do_move(clone)

        if not validates_after(tree, mutate):
            return SkipReason.InvalidStructure
        return None

    @staticmethod
    def _is_noop(
        source_parent: ChildContainer,
        source_index: int,
        dest_parent: ChildContainer,
        dest_index: int,
    ) -> bool:
        # `dest_index` is the pre-lift insertion index. After lifting at
        # source_index, inserting at source_index or source_index + 1 both
        # land the node back in its original slot.
        if source_parent is not dest_parent:
            return False
        return dest_index == source_index or dest_index == source_index + 1

    def _do_move(self, tree: Document) -> None:
        source = find_parent_and_index(tree, self.node_id)
        assert source is not None
        source_parent, source_index = source
        node = children_of(source_parent)[source_index]

        dest = resolve_anchor(tree, self.anchor)
        assert dest is not None
        dest_parent, dest_index = dest

        will_cleanup = isinstance(source_parent, List) and len(source_parent.children) == 1
        source_ordered = source_parent.ordered if isinstance(source_parent, List) else None

        children_of(source_parent).pop(source_index)

        if dest_parent is source_parent and dest_index > source_index:
            dest_index -= 1

        if will_cleanup:
            gp = find_parent_of_node(tree, source_parent)
            assert gp is not None
            gp_parent, gp_index = gp
            children_of(gp_parent).pop(gp_index)
            if dest_parent is gp_parent and dest_index > gp_index:
                dest_index -= 1

        insertion_node: PromptNode = node
        if isinstance(node, ListItem) and not isinstance(dest_parent, List):
            ordered = source_ordered if source_ordered is not None else False
            insertion_node = List(ordered=ordered, children=[node])
        elif isinstance(node, Section):
            new_level = section_level_for_parent(tree, dest_parent)
            if new_level is not None and new_level != node.level:
                _shift_section_levels(node, new_level - node.level)

        children_of(dest_parent).insert(dest_index, insertion_node)

    def apply(self, tree: Document, ctx: ApplyContext | None = None) -> None:
        self._do_move(tree)


def _shift_section_levels(root: Section, delta: int) -> None:
    for d in walk_all(root):
        if isinstance(d, Section):
            d.level += delta


@register("move_node")
def _build_move_node(raw: dict) -> Action | SkipReason:
    node_id = raw.get("id")
    if not isinstance(node_id, str) or not node_id:
        return SkipReason.MissingRequired
    anchor = parse_anchor(raw)
    if anchor is None:
        return SkipReason.MissingRequired
    return MoveNodeAction(node_id, anchor)
