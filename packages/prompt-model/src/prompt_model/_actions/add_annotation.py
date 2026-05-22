from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, Field

from .._prompt import (
    Annotation,
    Document,
    ExamplesGroup,
    GuidanceGroup,
    ListItem,
    Paragraph,
)
from .._utils import pydantic_aliases as py_types
from ._walk import walk_all, walk_annotatable
from .anchor import LocationAnchor, parse_anchor
from .protocol import Action, ApplyContext, SkipReason
from .registry import register
from .update_annotation import _BLOCK_MARKER_RE

_AnchorPosition = Literal["before", "after", "inside"]

_AnnotationKind = Literal["example", "guidance"]


class _AddAnnotationBase:
    kind: ClassVar[_AnnotationKind]

    def __init__(self, host_id: str, text: str, anchor: LocationAnchor | None = None) -> None:
        self.host_id = host_id
        self.text = text
        self.anchor = anchor

    def _attr(self) -> str:
        return "examples" if self.kind == "example" else "guidance"

    def _validate_text(self) -> SkipReason | None:
        if not self.text.strip() or ":::" in self.text:
            return SkipReason.InvalidContent
        if _BLOCK_MARKER_RE.search(self.text):
            return SkipReason.InvalidContent
        return None

    def _find_host(self, tree: Document) -> Paragraph | ListItem | None:
        for node in walk_annotatable(tree):
            if node.id == self.host_id:
                return node
        return None

    def _validate_anchor(self, host: Paragraph | ListItem) -> SkipReason | None:
        if self.anchor is None:
            return None
        target = self.anchor.target
        if self.anchor.position == "inside":
            if isinstance(target, str):
                if target != self.host_id:
                    return SkipReason.InvalidAnchor
            elif target is not host:
                return SkipReason.InvalidAnchor
            # inside is strict: only valid when the host has no group of the
            # relevant kind (empty groups are not a normal state).
            group = getattr(host, self._attr())
            if group is not None and group.children:
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
            for node in walk_all(tree):
                if getattr(node, "id", None) == self.host_id:
                    return SkipReason.HostNotAnnotatable
            return SkipReason.TargetNotFound
        return self._validate_anchor(host)

    def apply(self, tree: Document, ctx: ApplyContext | None = None) -> None:
        if ctx is None:
            ctx = ApplyContext.from_tree(tree)
        host = self._find_host(tree)
        assert host is not None, "apply() called without a successful validate()"
        annotation = Annotation(text=self.text)
        annotation.id = ctx.mint_annotation_id(host.id or self.host_id, self.kind)
        attr = self._attr()
        group = getattr(host, attr)
        if group is None:
            group_cls = ExamplesGroup if self.kind == "example" else GuidanceGroup
            setattr(host, attr, group_cls(children=[annotation]))
        else:
            group.children.insert(self._resolve_index(group), annotation)

    def _resolve_index(self, group: ExamplesGroup | GuidanceGroup) -> int:
        if self.anchor is None:
            return len(group.children)
        if self.anchor.position == "inside":
            # inside is only valid when the group was empty/missing — the
            # group passed here was just freshly created, so index 0.
            return 0
        target = self.anchor.target
        for i, ann in enumerate(group.children):
            matches = ann.id == target if isinstance(target, str) else ann is target
            if matches:
                return i + 1 if self.anchor.position == "after" else i
        return len(group.children)


class AddExampleAction(_AddAnnotationBase):
    kind: ClassVar[_AnnotationKind] = "example"


class AddGuidanceAction(_AddAnnotationBase):
    kind: ClassVar[_AnnotationKind] = "guidance"


def _build(cls: type[_AddAnnotationBase], raw: dict) -> Action | SkipReason:
    host_id = raw.get("host_id")
    text = raw.get("text")
    if not isinstance(host_id, str) or not host_id:
        return SkipReason.MissingRequired
    if not isinstance(text, str) or not text.strip():
        return SkipReason.MissingRequired
    # target + position are optional (both must appear together, or both
    # absent). If exactly one is present, treat as malformed → skip.
    has_target = "target" in raw
    has_position = "position" in raw
    anchor: LocationAnchor | None = None
    if has_target or has_position:
        if not (has_target and has_position):
            return SkipReason.MissingRequired
        anchor = parse_anchor(raw)
        if anchor is None:
            return SkipReason.MissingRequired
    return cls(host_id, text, anchor)


@register("add_example")
def _build_add_example(raw: dict) -> Action | SkipReason:
    return _build(AddExampleAction, raw)


@register("add_guidance")
def _build_add_guidance(raw: dict) -> Action | SkipReason:
    return _build(AddGuidanceAction, raw)


def _permissive_anchor(target: str | None, position: _AnchorPosition | None) -> LocationAnchor | None:
    """Build an anchor from optional target/position fields.

    Per the brainstorm decision: schema-level optionality + executor-level
    permissive handling. Target without position defaults position to "after".
    Position without target ignores both and appends at end.
    """
    if target is None:
        return None
    return LocationAnchor(target=target, position=position or "after")


class _AddAnnotationInputBase(BaseModel):
    host_id: py_types.NonBlankStr = Field(description="Id of the Paragraph or ListItem to attach the annotation to.")
    text: py_types.NonBlankStr = Field(description="The annotation text.")
    target: py_types.NonBlankStr | None = Field(
        default=None,
        description=("Optional placement anchor: an annotation id in the host's group, or the host id itself when position is 'inside'."),
    )
    position: _AnchorPosition | None = Field(
        default=None,
        description="Optional placement relative to target. Omit both target and position to append at end.",
    )


class AddExampleInput(_AddAnnotationInputBase):
    """LLM-output schema for `add_example`. Converts to AddExampleAction."""

    action: Literal["add_example"]

    def to_action(self) -> Action:
        return AddExampleAction(self.host_id, self.text, _permissive_anchor(self.target, self.position))


class AddGuidanceInput(_AddAnnotationInputBase):
    """LLM-output schema for `add_guidance`. Converts to AddGuidanceAction."""

    action: Literal["add_guidance"]

    def to_action(self) -> Action:
        return AddGuidanceAction(self.host_id, self.text, _permissive_anchor(self.target, self.position))
