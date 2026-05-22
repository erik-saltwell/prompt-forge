from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, Field

from .._prompt import Document, ListItem, Paragraph
from .._utils import pydantic_aliases as py_types
from ._walk import walk_annotatable
from .protocol import Action, ApplyContext, SkipReason
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

    def apply(self, tree: Document, ctx: ApplyContext | None = None) -> None:
        located = _find_host_and_index(tree, self.annotation_id, self.kind)
        assert located is not None, "apply() called without a successful validate()"
        host, index = located
        attr = _attr_for(self.kind)
        group = getattr(host, attr)
        assert group is not None
        group.children.pop(index)
        if not group.children:
            setattr(host, attr, None)


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


class RemoveExampleInput(BaseModel):
    """LLM-output schema for `remove_example`. Converts to RemoveExampleAction."""

    action: Literal["remove_example"]
    id: py_types.NonBlankStr = Field(description="Id of the example annotation to remove.")

    def to_action(self) -> Action:
        return RemoveExampleAction(self.id)


class RemoveGuidanceInput(BaseModel):
    """LLM-output schema for `remove_guidance`. Converts to RemoveGuidanceAction."""

    action: Literal["remove_guidance"]
    id: py_types.NonBlankStr = Field(description="Id of the guidance annotation to remove.")

    def to_action(self) -> Action:
        return RemoveGuidanceAction(self.id)
