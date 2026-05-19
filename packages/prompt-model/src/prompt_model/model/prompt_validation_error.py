from __future__ import annotations

from enum import StrEnum
from functools import total_ordering

from pydantic import BaseModel, NonNegativeInt

from .._utils import pydantic_aliases


class PromptErrorType(StrEnum):
    EmptyFile = "Empty File"
    HeadingLevelSkip = "Heading Level Skip"
    FirstHeadingNotH1 = "First Heading Not H1"
    EmptyHeading = "Empty Heading"
    HeadingInListItem = "Heading In List Item"
    EmptyListItem = "Empty List Item"
    MixedListTypeSiblings = "Mixed List Type Siblings"
    EmptyAnnotation = "Empty Annotation"
    OrphanAnnotation = "Orphan Annotation"
    IllegalAnnotationHost = "Illegal Annotation Host"
    HeadingInAnnotation = "Heading In Annotation"
    NestedAnnotation = "Nested Annotation"
    DuplicateAnnotationKind = "Duplicate Annotation Kind"
    IllegalAnnotationContent = "Illegal Annotation Content"
    NestedListInAnnotation = "Nested List In Annotation"
    AnnotationFenceInParagraph = "Annotation Fence In Paragraph"


@total_ordering
class PromptError(BaseModel):
    line: NonNegativeInt
    error_type: PromptErrorType
    error_message: pydantic_aliases.StrippedNonBlankStr

    def _comparison_key(self) -> tuple[int, str]:
        return self.line, self.error_type

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PromptError):
            return NotImplemented

        return self._comparison_key() == other._comparison_key()

    def __hash__(self) -> int:
        return hash(self._comparison_key())

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, PromptError):
            return NotImplemented

        return self._comparison_key() < other._comparison_key()
