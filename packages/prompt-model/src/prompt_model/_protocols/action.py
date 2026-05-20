from __future__ import annotations

from enum import StrEnum
from typing import Literal, Protocol

from ..model.nodes import Document

_AnnotationKind = Literal["example", "guidance"]


class SkipReason(StrEnum):
    UnknownType = "unknown_type"
    MissingRequired = "missing_required"
    TargetNotFound = "target_not_found"
    InvalidAnchor = "invalid_anchor"
    HostNotAnnotatable = "host_not_annotatable"
    DuplicateAnnotation = "duplicate_annotation"
    AnnotationNotFound = "annotation_not_found"
    InvalidContent = "invalid_content"
    InvalidSubtree = "invalid_subtree"
    InvalidStructure = "invalid_structure"


class ApplyContext:
    """Per-batch state threaded through `Action.apply()`.

    Holds the set of annotation IDs claimed so far in the batch.
    `mint_annotation_id` yields a fresh ID that has never been claimed,
    preventing collisions when multiple annotations are added in one batch.

    Use `ApplyContext.from_tree(tree)` to seed from a tree's current IDs.
    Passing `None` builds one ad-hoc — correct for one-off calls but
    skips cross-action collision protection.
    """

    def __init__(self, snapshot_ids: set[str] | None = None) -> None:
        self._claimed: set[str] = set(snapshot_ids) if snapshot_ids else set()

    @classmethod
    def from_tree(cls, tree: Document) -> ApplyContext:
        return cls(_collect_ids(tree))

    def mint_annotation_id(self, host_id: str, kind: _AnnotationKind) -> str:
        prefix = "e" if kind == "example" else "g"
        n = 1
        while True:
            candidate = f"{host_id}.{prefix}{n}"
            if candidate not in self._claimed:
                self._claimed.add(candidate)
                return candidate
            n += 1


def _collect_ids(tree: Document) -> set[str]:
    ids: set[str] = set()

    def visit(node: object) -> None:
        node_id = getattr(node, "id", None)
        if isinstance(node_id, str):
            ids.add(node_id)
        for attr in ("children", "examples", "guidance"):
            value = getattr(node, attr, None)
            if value is None:
                continue
            if isinstance(value, list):
                for child in value:
                    visit(child)
            else:
                visit(value)

    visit(tree)
    return ids


class Action(Protocol):
    def validate(self, tree: Document) -> SkipReason | None: ...

    def apply(self, tree: Document, ctx: ApplyContext | None = None) -> None: ...
