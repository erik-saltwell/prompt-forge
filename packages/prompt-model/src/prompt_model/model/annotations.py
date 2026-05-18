from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from .._utils.pydantic_aliases import StrippedNonBlankStr


class AnnotationType(StrEnum):
    Example = "ExampleAnnotation"
    Guidance = "GuidanceAnnotation"


class ExampleAnnotation(BaseModel):
    kind: Literal[AnnotationType.Example] = AnnotationType.Example
    id: str | None = None
    text: StrippedNonBlankStr


class GuidanceAnnotation(BaseModel):
    kind: Literal[AnnotationType.Guidance] = AnnotationType.Guidance
    id: str | None = None
    text: StrippedNonBlankStr
