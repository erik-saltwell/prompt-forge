from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, cast

from ...model import Document, List, ListItem, Paragraph, PromptNode, Section

if TYPE_CHECKING:
    from .anchor import LocationAnchor

type ChildContainer = Document | Section | List | ListItem


def child_container(node: PromptNode | None) -> ChildContainer | None:
    if isinstance(node, (Document, Section, List, ListItem)):
        return node
    return None


def children_of(node: ChildContainer) -> list[PromptNode]:
    return cast("list[PromptNode]", node.children)


def walk_all(node: PromptNode) -> Iterator[PromptNode]:
    yield node
    for child in getattr(node, "children", None) or ():
        yield from walk_all(child)


def walk_annotatable(node: PromptNode) -> Iterator[Paragraph | ListItem]:
    if isinstance(node, (Paragraph, ListItem)):
        yield node
    for child in getattr(node, "children", None) or ():
        yield from walk_annotatable(child)


def find_node_by_id(tree: Document, target_id: str) -> PromptNode | None:
    for node in walk_all(tree):
        if getattr(node, "id", None) == target_id:
            return node
    return None


def find_parent_and_index(tree: Document, target_id: str) -> tuple[ChildContainer, int] | None:
    """Locate the structural parent (Document/Section/List/ListItem) whose
    `children` list contains the node with `target_id`, plus the child's
    index. Returns None if the target is not found or is the Document
    itself (Document has no parent)."""
    for parent in walk_all(tree):
        container = child_container(parent)
        if container is None:
            continue
        children = children_of(container)
        for index, child in enumerate(children):
            if getattr(child, "id", None) == target_id:
                return container, index
    return None


def find_parent_of_node(tree: Document, node: PromptNode) -> tuple[ChildContainer, int] | None:
    """Like `find_parent_and_index` but matches by *identity*, not by id.
    Used when the target was created mid-batch and has no id yet (e.g.,
    an auto-wrap List inserted by move_node)."""
    for parent in walk_all(tree):
        container = child_container(parent)
        if container is None:
            continue
        for index, child in enumerate(children_of(container)):
            if child is node:
                return container, index
    return None


def resolve_anchor(tree: Document, anchor: LocationAnchor) -> tuple[ChildContainer, int] | None:
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


def anchor_for_slot(parent: ChildContainer, index: int) -> LocationAnchor | None:
    """Build a LocationAnchor that reconstructs the slot occupied by
    `parent.children[index]`, called *before* that occupant is removed.

    The occupant at `index` is excluded from the anchor candidates — it is
    the node being lifted out, so it cannot anchor its own slot.

    Resolution order:
    - if there is a previous sibling at `index - 1`, anchor `after` it;
    - else if there is a next sibling at `index + 1`, anchor `before` it;
    - else (parent will be empty after the remove) anchor `first_child` of parent.

    Returns None if no anchor can be built — currently only when `parent` is
    a Document with no surviving sibling (Document has no id)."""
    siblings = children_of(parent)
    from .anchor import LocationAnchor

    # LocationAnchor.target accepts either a string id or a PromptNode
    # reference. We prefer ids for stability (refs require the node object
    # to remain reachable through undo), but fall back to refs when the
    # target has no id — e.g., an anonymous wrap List created mid-batch by
    # move_node, or the Document root.
    if index > 0:
        prev = siblings[index - 1]
        if prev.id is not None:
            return LocationAnchor(kind="after", target=prev.id)
        return LocationAnchor(kind="after", target=prev)
    if index + 1 < len(siblings):
        nxt = siblings[index + 1]
        if nxt.id is not None:
            return LocationAnchor(kind="before", target=nxt.id)
        return LocationAnchor(kind="before", target=nxt)
    parent_id = parent.id
    if parent_id is not None:
        return LocationAnchor(kind="first_child", target=parent_id)
    if isinstance(parent, Document):
        return None
    return LocationAnchor(kind="first_child", target=parent)


def is_descendant(node: PromptNode, possible_ancestor: PromptNode) -> bool:
    """True if `node` is `possible_ancestor` or appears anywhere in its subtree."""
    for d in walk_all(possible_ancestor):
        if d is node:
            return True
    return False


def path_to_container(tree: Document, target: ChildContainer) -> list[ChildContainer] | None:
    """Return the chain of ChildContainer ancestors from `tree` down to and
    including `target`. Returns None if `target` is not found."""
    path: list[ChildContainer] = []

    def visit(parent: ChildContainer) -> bool:
        path.append(parent)
        if parent is target:
            return True
        for child in children_of(parent):
            sub = child_container(child)
            if sub is not None and visit(sub):
                return True
        path.pop()
        return False

    return path if visit(tree) else None


def section_level_for_parent(tree: Document, parent: ChildContainer) -> int | None:
    """The Section.level a freshly-inserted Section should carry if placed as
    a direct child of `parent`. Returns the deepest Section ancestor's level
    plus one, or 1 if there is no Section ancestor. Returns None if `parent`
    cannot host a Section (e.g., List, ListItem)."""
    if not isinstance(parent, (Document, Section)):
        return None
    path = path_to_container(tree, parent)
    if path is None:
        return None
    depth = 0
    for ancestor in path:
        if isinstance(ancestor, Section):
            depth = max(depth, ancestor.level)
    return depth + 1


def is_empty_container(node: PromptNode) -> bool:
    """Shallow check: `node` is a Section or List with no children. These
    cannot be reserialised to conforming markdown and must be removed when
    an action empties them."""
    return isinstance(node, (Section, List)) and not node.children


def has_empty_container(node: PromptNode) -> bool:
    """Deep check: `node` or any descendant is an empty Section/List.
    ListItem has its own `text` so an item with no body children is still
    meaningful and is not flagged."""
    if is_empty_container(node):
        return True
    children = getattr(node, "children", None) or ()
    return any(has_empty_container(c) for c in children)
