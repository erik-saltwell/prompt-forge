from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from ...model import Document, List, ListItem, Paragraph, PromptNode, Section

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
