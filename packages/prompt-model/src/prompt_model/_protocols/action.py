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

    Holds the set of node/annotation IDs that are "claimed" — both those
    present in the frozen snapshot at batch start and any minted during
    earlier `apply()` calls in the same batch. `mint_annotation_id`
    yields a fresh ID that has never been claimed; this is what an
    `AddExampleAction` / `AddGuidanceAction` stamps onto the freshly
    inserted annotation so its inverse can address it by ID.

    Use `ApplyContext.from_tree(tree)` to seed from a tree's current IDs.
    Action methods accept `ctx: ApplyContext | None`; passing `None`
    builds one ad-hoc, which is correct for one-off calls but defeats
    the cross-action collision protection that a real batch needs.
    """

    def __init__(self, snapshot_ids: set[str] | None = None) -> None:
        self._claimed: set[str] = set(snapshot_ids) if snapshot_ids else set()

    @classmethod
    def from_tree(cls, tree: Document) -> ApplyContext:
        return cls(_collect_ids(tree))

    def mint_inserted_node_id(self) -> str:
        """Mint a synthetic id for a node inserted mid-batch.

        Node ids are normally position-derived ("2.1.3"), but a newly
        inserted node has no natural id until assign_ids re-runs at end
        of batch. The inverse RemoveNodeAction needs to address the new
        node, so we stamp a synthetic id guaranteed not to collide."""
        n = 1
        while True:
            candidate = f"__inserted_{n}__"
            if candidate not in self._claimed:
                self._claimed.add(candidate)
                return candidate
            n += 1

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

    def apply(self, tree: Document, ctx: ApplyContext | None = None) -> Action: ...
