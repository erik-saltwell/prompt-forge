from __future__ import annotations

from ..._protocols.action import Action, ApplyContext, SkipReason
from ...model import Document, List, ListItem, PromptNode, Section
from ._dry_run import validates_after
from ._walk import (
    ChildContainer,
    anchor_for_slot,
    children_of,
    find_parent_and_index,
    find_parent_of_node,
    is_descendant,
    resolve_anchor,
    section_level_for_parent,
    walk_all,
)
from .anchor import LocationAnchor, parse_anchor
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

    The inverse is a single `MoveNodeAction` targeting the node back to its
    original slot. When the source list was removed, the inverse anchor
    points at the list's old slot in its grandparent — the auto-wrap rule
    naturally recreates an equivalent List on the way back."""

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

    def _do_move(self, tree: Document) -> Action | list[Action]:
        """Execute the move on `tree` and return the inverse Action(s).

        Used both by `apply` (on the real tree) and `validates_after`
        (on a clone, where the inverse is discarded). Both paths resolve
        the source and destination by id against the given tree, so the
        clone is handled transparently."""
        source = find_parent_and_index(tree, self.node_id)
        assert source is not None
        source_parent, source_index = source
        node = children_of(source_parent)[source_index]

        dest = resolve_anchor(tree, self.anchor)
        assert dest is not None
        dest_parent, dest_index = dest

        # Cleanup path: when the source list will be emptied by lifting the
        # node, we capture a deep copy of the original source list so the
        # inverse can restore it verbatim — preserving its id, `ordered`
        # flag, and any sibling ListItems that don't exist (only-child
        # case). Without this, later inverses in a batch that reference the
        # source list's id would fail because the live tree no longer
        # contains it (the simple MoveNode inverse would have created a
        # fresh anonymous wrap list instead).
        will_cleanup = isinstance(source_parent, List) and len(source_parent.children) == 1
        captured_source_list: List | None = None
        gp_anchor: LocationAnchor | None = None
        if will_cleanup:
            assert isinstance(source_parent, List)
            gp = find_parent_of_node(tree, source_parent)
            assert gp is not None
            gp_parent_cap, gp_index_cap = gp
            gp_anchor = anchor_for_slot(gp_parent_cap, gp_index_cap)
            assert gp_anchor is not None
            captured_source_list = source_parent.model_copy(deep=True)

        default_inverse_anchor = anchor_for_slot(source_parent, source_index)
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

        if will_cleanup:
            assert captured_source_list is not None
            assert gp_anchor is not None
            was_wrapped = insertion_node is not node
            # Inverse locates the moved listitem by id (stable through
            # intermediate undo/redo, including any subsequent cleanup that
            # might deep-copy the auto-wrap). Then restores the captured
            # source List verbatim at the gp slot.
            return _CleanupInverse(self.node_id, was_wrapped, captured_source_list, gp_anchor)
        assert default_inverse_anchor is not None
        return MoveNodeAction(self.node_id, default_inverse_anchor)

    def apply(self, tree: Document, ctx: ApplyContext | None = None) -> Action | list[Action]:
        return self._do_move(tree)


def _shift_section_levels(root: Section, delta: int) -> None:
    for d in walk_all(root):
        if isinstance(d, Section):
            d.level += delta


class _CleanupInverse:
    """Private inverse of a `MoveNodeAction` that triggered source-list
    cleanup. Lifts the moved ListItem from wherever it currently sits
    (located by snapshot id, which is preserved across intermediate
    moves), removes the auto-wrap List too if one was created on the
    forward, and restores the captured source List at the grandparent
    slot.

    Not part of the public action vocabulary: never registered, never
    parsed from JSON, never returned by anything except `MoveNodeAction`.
    Its own apply returns `self` because we don't expect anyone to redo
    an undo of this shape in the same batch."""

    def __init__(
        self,
        node_id: str,
        was_wrapped: bool,
        captured_source_list: List,
        gp_anchor: LocationAnchor,
    ) -> None:
        self._node_id = node_id
        self._was_wrapped = was_wrapped
        self._captured = captured_source_list
        self._gp_anchor = gp_anchor

    def validate(self, tree: Document) -> SkipReason | None:
        return None

    def apply(self, tree: Document, ctx: ApplyContext | None = None) -> Action:
        loc = find_parent_and_index(tree, self._node_id)
        assert loc is not None, "_CleanupInverse: moved node not found by id"
        parent, index = loc
        children_of(parent).pop(index)

        if self._was_wrapped:
            # The listitem's parent was an auto-wrap List with no id; it
            # is now empty after the lift. Remove it from its grandparent
            # so the tree shape matches pre-forward.
            wrap_loc = find_parent_of_node(tree, parent)
            assert wrap_loc is not None, "_CleanupInverse: wrap parent missing"
            wp, wi = wrap_loc
            children_of(wp).pop(wi)

        dest = resolve_anchor(tree, self._gp_anchor)
        assert dest is not None, "_CleanupInverse: gp anchor did not resolve"
        gp_parent, gp_index = dest
        children_of(gp_parent).insert(gp_index, self._captured)
        return self


@register("move_node")
def _build_move_node(raw: dict) -> Action | SkipReason:
    node_id = raw.get("id")
    if not isinstance(node_id, str) or not node_id:
        return SkipReason.MissingRequired
    anchor_raw = raw.get("anchor")
    if not isinstance(anchor_raw, dict):
        return SkipReason.MissingRequired
    anchor = parse_anchor(anchor_raw)
    if anchor is None:
        return SkipReason.MissingRequired
    return MoveNodeAction(node_id, anchor)
