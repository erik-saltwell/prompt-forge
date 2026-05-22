from __future__ import annotations

from typing import Protocol

from .._prompt import Document
from ._xml import to_xml

DOCUMENT_SENTINEL: str = "document"


class RedactionStrategy(Protocol):
    """Given a tree and a culprit node id, returns the XML the actor will see."""

    def render(self, tree: Document, culprit_node_id: str) -> str: ...


class DefaultRedactionStrategy:
    """Skeleton render: every node keeps id + structure; content kept for the
    culprit node, its ancestors, its siblings, and the culprit's own annotations
    (or sibling annotations if the culprit is itself an annotation).

    When culprit is the document sentinel, the full content is rendered.
    """

    def render(self, tree: Document, culprit_node_id: str) -> str:
        if culprit_node_id == DOCUMENT_SENTINEL:
            return to_xml(tree, focus_ids=None)
        focus: set[str] = self._focus_ids(tree, culprit_node_id)
        return to_xml(tree, focus_ids=focus)

    def _focus_ids(self, tree: Document, target_id: str) -> set[str]:
        focus: set[str] = {target_id}
        path: list[object] = _path_to(tree, target_id)
        if not path:
            return focus
        # path is [root_section, ..., parent, target] when target is found
        target = path[-1]
        # Ancestors: every non-document, non-target node on the path
        for ancestor in path[:-1]:
            aid = getattr(ancestor, "id", None)
            if isinstance(aid, str):
                focus.add(aid)
        # Section headings always: included by walking the entire tree
        focus |= _all_section_ids(tree)
        # Siblings of target: take siblings from parent
        parent: object = path[-2] if len(path) >= 2 else tree
        for sib in _children(parent):
            sid = getattr(sib, "id", None)
            if isinstance(sid, str):
                focus.add(sid)
        # Target's own annotations (paragraph/listitem hosting)
        for grp_attr in ("examples", "guidance"):
            grp = getattr(target, grp_attr, None)
            if grp is None:
                continue
            for ann in grp.children:
                if isinstance(ann.id, str):
                    focus.add(ann.id)
        # If target is an annotation, also focus its group siblings
        if _is_annotation(target):
            group_parent: object | None = _find_annotation_host(tree, target_id)
            if group_parent is not None:
                for grp_attr in ("examples", "guidance"):
                    grp = getattr(group_parent, grp_attr, None)
                    if grp is None:
                        continue
                    for ann in grp.children:
                        if isinstance(ann.id, str) and ann.id == target_id:
                            for sib in grp.children:
                                if isinstance(sib.id, str):
                                    focus.add(sib.id)
        return focus


def _children(node: object) -> list[object]:
    out: list[object] = []
    val = getattr(node, "children", None)
    if isinstance(val, list):
        out.extend(val)
    return out


def _all_section_ids(tree: Document) -> set[str]:
    ids: set[str] = set()

    def walk(node: object) -> None:
        from .._prompt.nodes import Section

        if isinstance(node, Section) and isinstance(node.id, str):
            ids.add(node.id)
        for c in _children(node):
            walk(c)

    walk(tree)
    return ids


def _path_to(tree: Document, target_id: str) -> list[object]:
    """DFS from root; return the chain of nodes ending at the node with id == target_id, inclusive."""
    found: list[object] = []

    def walk(node: object, trail: list[object]) -> bool:
        nid = getattr(node, "id", None)
        new_trail = trail + [node] if not isinstance(node, Document) else trail
        if isinstance(nid, str) and nid == target_id:
            found.extend(new_trail)
            return True
        for c in _children(node):
            if walk(c, new_trail):
                return True
        for grp_attr in ("examples", "guidance"):
            grp = getattr(node, grp_attr, None)
            if grp is None:
                continue
            for ann in grp.children:
                if isinstance(ann.id, str) and ann.id == target_id:
                    found.extend(new_trail + [ann])
                    return True
        return False

    walk(tree, [])
    return found


def _is_annotation(node: object) -> bool:
    from .._prompt.annotations import Annotation

    return isinstance(node, Annotation)


def _find_annotation_host(tree: Document, ann_id: str) -> object | None:
    """Return the Paragraph/ListItem that hosts the annotation, by walking the tree."""
    result: list[object] = []

    def walk(node: object) -> None:
        for grp_attr in ("examples", "guidance"):
            grp = getattr(node, grp_attr, None)
            if grp is None:
                continue
            for ann in grp.children:
                if isinstance(ann.id, str) and ann.id == ann_id:
                    result.append(node)
                    return
        for c in _children(node):
            walk(c)

    walk(tree)
    return result[0] if result else None
