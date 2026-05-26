from __future__ import annotations

from ..._prompt import Annotation, Document, Section

DOCUMENT_SENTINEL: str = "document"


class ContextualRedactionStrategy:
    """Focus on the culprit, its ancestors, its siblings, its own annotations
    (or sibling annotations if the culprit is itself an annotation), plus every
    section heading in the tree.

    When culprit is the document sentinel, returns `None` (full content visible).
    """

    def focus_ids(self, tree: Document, culprit_node_id: str) -> set[str] | None:
        if culprit_node_id == DOCUMENT_SENTINEL:
            return None
        focus: set[str] = {culprit_node_id}
        path: list[object] = _path_to(tree, culprit_node_id)
        if not path:
            return focus
        target = path[-1]
        for ancestor in path[:-1]:
            aid = getattr(ancestor, "id", None)
            if isinstance(aid, str):
                focus.add(aid)
        focus |= _all_section_ids(tree)
        parent: object = path[-2] if len(path) >= 2 else tree
        for sib in _children(parent):
            sid = getattr(sib, "id", None)
            if isinstance(sid, str):
                focus.add(sid)
        for grp_attr in ("examples", "guidance"):
            grp = getattr(target, grp_attr, None)
            if grp is None:
                continue
            for ann in grp.children:
                if isinstance(ann.id, str):
                    focus.add(ann.id)
        if _is_annotation(target):
            group_parent: object | None = _find_annotation_host(tree, culprit_node_id)
            if group_parent is not None:
                for grp_attr in ("examples", "guidance"):
                    grp = getattr(group_parent, grp_attr, None)
                    if grp is None:
                        continue
                    for ann in grp.children:
                        if isinstance(ann.id, str) and ann.id == culprit_node_id:
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
        if isinstance(node, Section) and isinstance(node.id, str):
            ids.add(node.id)
        for c in _children(node):
            walk(c)

    walk(tree)
    return ids


def _path_to(tree: Document, target_id: str) -> list[object]:
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
    return isinstance(node, Annotation)


def _find_annotation_host(tree: Document, ann_id: str) -> object | None:
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
