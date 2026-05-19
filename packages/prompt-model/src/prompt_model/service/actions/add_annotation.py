from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar, Literal

from ..._protocols.action import Action, ApplyContext, SkipReason
from ...model import (
    Annotation,
    Document,
    ExamplesGroup,
    GuidanceGroup,
    ListItem,
    Paragraph,
    PromptNode,
)
from .anchor import LocationAnchor, parse_anchor
from .registry import register
from .remove_annotation import RemoveExampleAction, RemoveGuidanceAction
from .update_annotation import _BLOCK_MARKER_RE, _walk_annotatable

_AnnotationKind = Literal["example", "guidance"]


def _walk_all(node: PromptNode) -> Iterator[PromptNode]:
    yield node
    for child in getattr(node, "children", None) or ():
        yield from _walk_all(child)


class _AddAnnotationBase:
    kind: ClassVar[_AnnotationKind]

    def __init__(self, host_id: str, text: str, anchor: LocationAnchor | None = None) -> None:
        self.host_id = host_id
        self.text = text
        self.anchor = anchor
        # Set only when this Add is constructed as the inverse of a Remove
        # (via `_for_undo`). Carries the original Annotation object so undo
        # restores the snapshot id, which keeps prev-sibling anchors stable
        # across multi-action batches under LIFO undo.
        self._captured: Annotation | None = None

    @classmethod
    def _for_undo(
        cls,
        host_id: str,
        annotation: Annotation,
        anchor: LocationAnchor | None,
    ) -> _AddAnnotationBase:
        action = cls(host_id, annotation.text, anchor)
        action._captured = annotation
        return action

    def _attr(self) -> str:
        return "examples" if self.kind == "example" else "guidance"

    def _validate_text(self) -> SkipReason | None:
        if not self.text.strip() or ":::" in self.text:
            return SkipReason.InvalidContent
        if _BLOCK_MARKER_RE.search(self.text):
            return SkipReason.InvalidContent
        return None

    def _find_host(self, tree: Document) -> Paragraph | ListItem | None:
        for node in _walk_annotatable(tree):
            if node.id == self.host_id:
                return node
        return None

    def _validate_anchor(self, host: Paragraph | ListItem) -> SkipReason | None:
        if self.anchor is None:
            return None
        target = self.anchor.target
        if self.anchor.kind in ("first_child", "last_child"):
            if isinstance(target, str):
                if target != self.host_id:
                    return SkipReason.InvalidAnchor
            elif target is not host:
                return SkipReason.InvalidAnchor
            return None
        group = getattr(host, self._attr())
        if group is None:
            return SkipReason.InvalidAnchor
        if isinstance(target, str):
            if not any(ann.id == target for ann in group.children):
                return SkipReason.InvalidAnchor
        elif target not in group.children:
            return SkipReason.InvalidAnchor
        return None

    def validate(self, tree: Document) -> SkipReason | None:
        text_problem = self._validate_text()
        if text_problem is not None:
            return text_problem
        host = self._find_host(tree)
        if host is None:
            for node in _walk_all(tree):
                if getattr(node, "id", None) == self.host_id:
                    return SkipReason.HostNotAnnotatable
            return SkipReason.TargetNotFound
        return self._validate_anchor(host)

    def apply(self, tree: Document, ctx: ApplyContext | None = None) -> Action:
        if ctx is None:
            ctx = ApplyContext.from_tree(tree)
        host = self._find_host(tree)
        assert host is not None, "apply() called without a successful validate()"
        if self._captured is not None:
            # Undo path: re-insert the original Annotation with its snapshot id
            # (which the ctx already had claimed, so no collision risk).
            annotation = self._captured
        else:
            annotation = Annotation(text=self.text)
            annotation.id = ctx.mint_annotation_id(host.id or self.host_id, self.kind)
        attr = self._attr()
        group = getattr(host, attr)
        if group is None:
            group_cls = ExamplesGroup if self.kind == "example" else GuidanceGroup
            setattr(host, attr, group_cls(children=[annotation]))
        else:
            group.children.insert(self._resolve_index(group), annotation)
        inverse_cls = RemoveExampleAction if self.kind == "example" else RemoveGuidanceAction
        assert annotation.id is not None
        return inverse_cls(annotation.id)

    def _resolve_index(self, group: ExamplesGroup | GuidanceGroup) -> int:
        if self.anchor is None or self.anchor.kind == "last_child":
            return len(group.children)
        if self.anchor.kind == "first_child":
            return 0
        target = self.anchor.target
        for i, ann in enumerate(group.children):
            matches = ann.id == target if isinstance(target, str) else ann is target
            if matches:
                return i + 1 if self.anchor.kind == "after" else i
        return len(group.children)


class AddExampleAction(_AddAnnotationBase):
    kind: ClassVar[_AnnotationKind] = "example"


class AddGuidanceAction(_AddAnnotationBase):
    kind: ClassVar[_AnnotationKind] = "guidance"


def _build(cls: type[_AddAnnotationBase], raw: dict) -> Action | SkipReason:
    host_id = raw.get("host_id")
    text = raw.get("text")
    anchor_raw = raw.get("anchor")
    if not isinstance(host_id, str) or not host_id:
        return SkipReason.MissingRequired
    if not isinstance(text, str) or not text.strip():
        return SkipReason.MissingRequired
    anchor: LocationAnchor | None = None
    if anchor_raw is not None:
        if not isinstance(anchor_raw, dict):
            return SkipReason.MissingRequired
        anchor = parse_anchor(anchor_raw)
        if anchor is None:
            return SkipReason.MissingRequired
    return cls(host_id, text, anchor)


@register("add_example")
def _build_add_example(raw: dict) -> Action | SkipReason:
    return _build(AddExampleAction, raw)


@register("add_guidance")
def _build_add_guidance(raw: dict) -> Action | SkipReason:
    return _build(AddGuidanceAction, raw)
