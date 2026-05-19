from __future__ import annotations

from typing import ClassVar, Literal

from ..._protocols.action import Action, ApplyContext, SkipReason
from ...model import Document, ListItem, Paragraph
from ._walk import walk_annotatable
from .anchor import LocationAnchor
from .registry import register

_AnnotationKind = Literal["example", "guidance"]


def _attr_for(kind: _AnnotationKind) -> str:
    return "examples" if kind == "example" else "guidance"


def _find_host_and_index(tree: Document, annotation_id: str, kind: _AnnotationKind) -> tuple[Paragraph | ListItem, int] | None:
    attr = _attr_for(kind)
    for host in walk_annotatable(tree):
        group = getattr(host, attr)
        if group is None:
            continue
        for index, ann in enumerate(group.children):
            if ann.id == annotation_id:
                return host, index
    return None


class _RemoveAnnotationBase:
    kind: ClassVar[_AnnotationKind]

    def __init__(self, annotation_id: str) -> None:
        self.annotation_id = annotation_id

    def validate(self, tree: Document) -> SkipReason | None:
        if _find_host_and_index(tree, self.annotation_id, self.kind) is None:
            return SkipReason.AnnotationNotFound
        return None

    def apply(self, tree: Document, ctx: ApplyContext | None = None) -> Action:
        # Local import avoids a circular dependency with add_annotation.py:
        # Add returns Remove as its inverse, Remove returns Add as its inverse.
        from .add_annotation import AddExampleAction, AddGuidanceAction

        located = _find_host_and_index(tree, self.annotation_id, self.kind)
        assert located is not None, "apply() called without a successful validate()"
        host, index = located
        attr = _attr_for(self.kind)
        group = getattr(host, attr)
        assert group is not None

        # Capture neighbour IDs *before* mutating so the inverse Add can
        # restore the exact slot via an `after`/`before` anchor. If the
        # removed annotation was the only child we need no anchor — Add
        # auto-creates the group.
        prev_id = group.children[index - 1].id if index > 0 else None
        has_next = index + 1 < len(group.children)
        host_id = host.id or ""

        # Capture the live Annotation (with its snapshot id) so the inverse
        # Add can re-insert the same object. Preserving the id keeps anchors
        # in other inverses on the undo stack from going stale under LIFO
        # undo — a sibling removed later is restored earlier, so by the time
        # our anchor needs to resolve, the target is back with its old id.
        annotation = group.children.pop(index)
        if not group.children:
            setattr(host, attr, None)

        # Anchor choice prioritises stability through batched undo. The host
        # id never changes during a batch, so `first_child target=host_id`
        # is preferred when restoring at index 0.
        anchor: LocationAnchor | None
        if prev_id is not None:
            anchor = LocationAnchor(kind="after", target=prev_id)
        elif has_next:
            anchor = LocationAnchor(kind="first_child", target=host_id)
        else:
            anchor = None  # group was torn down — Add will recreate it

        inverse_cls = AddExampleAction if self.kind == "example" else AddGuidanceAction
        return inverse_cls._for_undo(host_id, annotation, anchor)


class RemoveExampleAction(_RemoveAnnotationBase):
    kind: ClassVar[_AnnotationKind] = "example"


class RemoveGuidanceAction(_RemoveAnnotationBase):
    kind: ClassVar[_AnnotationKind] = "guidance"


def _build(cls: type[_RemoveAnnotationBase], raw: dict) -> Action | SkipReason:
    ann_id = raw.get("id")
    if not isinstance(ann_id, str) or not ann_id:
        return SkipReason.MissingRequired
    return cls(ann_id)


@register("remove_example")
def _build_remove_example(raw: dict) -> Action | SkipReason:
    return _build(RemoveExampleAction, raw)


@register("remove_guidance")
def _build_remove_guidance(raw: dict) -> Action | SkipReason:
    return _build(RemoveGuidanceAction, raw)
