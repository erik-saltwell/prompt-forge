from __future__ import annotations

import re
from typing import ClassVar, Literal

from ..._protocols.action import Action, ApplyContext, SkipReason
from ...model import Annotation, Document
from ._walk import walk_annotatable
from .registry import register

# A line starting (optionally indented) with an ATX heading (1-6 '#' + space)
# or an unordered-list marker (`- `) would, on round-trip through the
# generator, parse as a heading / list *inside* the annotation body — both
# are forbidden by the prompt-model annotation-content rules.
_BLOCK_MARKER_RE = re.compile(r"^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s)", re.MULTILINE)

_AnnotationKind = Literal["example", "guidance"]


def _find_annotation(tree: Document, annotation_id: str, kind: _AnnotationKind) -> Annotation | None:
    attr = "examples" if kind == "example" else "guidance"
    for host in walk_annotatable(tree):
        group = getattr(host, attr)
        if group is None:
            continue
        for ann in group.children:
            if ann.id == annotation_id:
                return ann
    return None


class _UpdateAnnotationBase:
    kind: ClassVar[_AnnotationKind]

    def __init__(self, annotation_id: str, text: str) -> None:
        self.annotation_id = annotation_id
        self.text = text

    def validate(self, tree: Document) -> SkipReason | None:
        if not self.text.strip() or ":::" in self.text:
            return SkipReason.InvalidContent
        if _BLOCK_MARKER_RE.search(self.text):
            return SkipReason.InvalidContent
        if _find_annotation(tree, self.annotation_id, self.kind) is None:
            return SkipReason.AnnotationNotFound
        return None

    def apply(self, tree: Document, ctx: ApplyContext | None = None) -> Action:
        ann = _find_annotation(tree, self.annotation_id, self.kind)
        assert ann is not None, "apply() called without a successful validate()"
        old_text = ann.text
        ann.text = self.text
        return type(self)(self.annotation_id, old_text)


class UpdateExampleAction(_UpdateAnnotationBase):
    kind: ClassVar[_AnnotationKind] = "example"


class UpdateGuidanceAction(_UpdateAnnotationBase):
    kind: ClassVar[_AnnotationKind] = "guidance"


def _build(cls: type[_UpdateAnnotationBase], raw: dict) -> Action | SkipReason:
    ann_id = raw.get("id")
    text = raw.get("text")
    if not isinstance(ann_id, str) or not ann_id:
        return SkipReason.MissingRequired
    if not isinstance(text, str) or not text.strip():
        return SkipReason.MissingRequired
    return cls(ann_id, text)


@register("update_example")
def _build_update_example(raw: dict) -> Action | SkipReason:
    return _build(UpdateExampleAction, raw)


@register("update_guidance")
def _build_update_guidance(raw: dict) -> Action | SkipReason:
    return _build(UpdateGuidanceAction, raw)
