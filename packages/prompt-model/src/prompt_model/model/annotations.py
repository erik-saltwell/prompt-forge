from __future__ import annotations

from typing import Literal

from .._utils.pydantic_aliases import StrippedNonBlankStr
from ._base import NodeType, PromptNode


def _fence(label: str, text: str) -> str:
    body = text.rstrip("\n")
    return f"::: {label}\n{body}\n:::"


class ExampleAnnotation(PromptNode):
    node_type: Literal[NodeType.ExampleAnnotation] = NodeType.ExampleAnnotation
    text: StrippedNonBlankStr

    def to_markdown(self) -> str:
        return _fence("examples", self.text)


class GuidanceAnnotation(PromptNode):
    node_type: Literal[NodeType.GuidanceAnnotation] = NodeType.GuidanceAnnotation
    text: StrippedNonBlankStr

    def to_markdown(self) -> str:
        return _fence("guidance", self.text)
