from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from ..model.nodes import Document


class SkipReason(StrEnum):
    UnknownType = "unknown_type"
    MissingRequired = "missing_required"
    TargetNotFound = "target_not_found"
    InvalidAnchor = "invalid_anchor"
    HostNotAnnotatable = "host_not_annotatable"
    DuplicateAnnotation = "duplicate_annotation"
    AnnotationNotFound = "annotation_not_found"
    InvalidContent = "invalid_content"


class Action(Protocol):
    def validate(self, tree: Document) -> SkipReason | None: ...

    def apply(self, tree: Document) -> Action: ...
