from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from ..prompt import Document, List, ListItem, Paragraph, PromptNode, Section
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
    `children` list. Returns None if the target doesn't resolve, the parent
    isn't a container, or `inside` is used on a container that already has
    children."""
    target = anchor.target
    if anchor.position == "inside":
        parent: ChildContainer | None
        if isinstance(target, str):
            parent = child_container(find_node_by_id(tree, target))
        else:
            parent = child_container(target) if target in walk_all(tree) else None
        if parent is None:
            return None
        if children_of(parent):
            return None
        return parent, 0

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
    return parent, index + (1 if anchor.position == "after" else 0)


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
