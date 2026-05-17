from typing import Annotated

from pydantic import Field, StringConstraints

type NonEmptyList[T] = Annotated[list[T], Field(min_length=1)]
type NonEmptyTuple[T] = Annotated[tuple[T, ...], Field(min_length=1)]

NonEmptyStr = Annotated[
    str,
    StringConstraints(min_length=1),
]

NonBlankStr = Annotated[
    str,
    StringConstraints(pattern=r"\S"),
]

StrippedNonBlankStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]
