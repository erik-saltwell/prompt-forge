from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field

from .._utils.pydantic_aliases import StrippedNonBlankStr
from ._base import NodeType, PromptNode


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line if line else "" for line in text.split("\n"))


class Annotation(PromptNode):
    node_type: Literal[NodeType.Annotation] = NodeType.Annotation
    text: StrippedNonBlankStr

    def to_markdown(self) -> str:
        return self.text


class _AnnotationGroup(PromptNode):
    """Common shape for ExamplesGroup and GuidanceGroup.

    Subclasses set `_label` (the directive name, e.g. `examples` or
    `guidance`). The group emits text form for a single child and list
    form for multiple children. A group is never empty.
    """

    _label: ClassVar[str]
    children: list[Annotation] = Field(default_factory=list, min_length=1)

    def to_markdown(self) -> str:
        if len(self.children) == 1:
            body = self.children[0].text.rstrip("\n")
        else:
            body = "\n".join(_render_list_item_text(c.text) for c in self.children)
        return f"::: {self._label}\n{body}\n:::"


def _render_list_item_text(text: str) -> str:
    first, _, rest = text.partition("\n")
    if not rest:
        return f"- {first}"
    return f"- {first}\n{_indent(rest, '  ')}"


class ExamplesGroup(_AnnotationGroup):
    node_type: Literal[NodeType.ExamplesGroup] = NodeType.ExamplesGroup
    _label: ClassVar[str] = "examples"


class GuidanceGroup(_AnnotationGroup):
    node_type: Literal[NodeType.GuidanceGroup] = NodeType.GuidanceGroup
    _label: ClassVar[str] = "guidance"
