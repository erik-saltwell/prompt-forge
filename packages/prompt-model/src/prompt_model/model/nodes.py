from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .._utils.pydantic_aliases import StrippedNonBlankStr
from ._base import NodeType, PromptNode
from .annotations import ExampleAnnotation, GuidanceAnnotation


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line if line else "" for line in text.split("\n"))


def _join_blocks(parts: list[str]) -> str:
    return "\n\n".join(p for p in parts if p)


class Paragraph(PromptNode):
    node_type: Literal[NodeType.Paragraph] = NodeType.Paragraph
    text: StrippedNonBlankStr
    example: ExampleAnnotation | None = None
    guidance: GuidanceAnnotation | None = None

    def to_markdown(self) -> str:
        parts = [self.text]
        if self.example is not None:
            parts.append(self.example.to_markdown())
        if self.guidance is not None:
            parts.append(self.guidance.to_markdown())
        return _join_blocks(parts)


class CodeBlock(PromptNode):
    node_type: Literal[NodeType.CodeBlock] = NodeType.CodeBlock
    text: str = ""
    info: str = ""

    def to_markdown(self) -> str:
        body = self.text.rstrip("\n")
        return f"```{self.info}\n{body}\n```"


class Blockquote(PromptNode):
    node_type: Literal[NodeType.Blockquote] = NodeType.Blockquote
    text: str = ""

    def to_markdown(self) -> str:
        return "\n".join(f"> {line}" if line else ">" for line in self.text.split("\n"))


class Table(PromptNode):
    node_type: Literal[NodeType.Table] = NodeType.Table
    text: str = ""

    def to_markdown(self) -> str:
        # Tables are stored as flattened text by the parser; emit verbatim.
        # Round-tripping a real table through the model is lossy by design.
        return self.text


class ListItem(PromptNode):
    node_type: Literal[NodeType.ListItem] = NodeType.ListItem
    text: StrippedNonBlankStr
    children: list[BlockChild] = Field(default_factory=list)
    example: ExampleAnnotation | None = None
    guidance: GuidanceAnnotation | None = None

    def to_markdown(self) -> str:
        return _render_list_item(self, marker="-")


class List(PromptNode):
    node_type: Literal[NodeType.List] = NodeType.List
    ordered: bool
    children: list[ListItem] = Field(default_factory=list)

    def to_markdown(self) -> str:
        # MD031: if any item carries a non-List block child (e.g. a fenced
        # code block), the list becomes "loose" — items are separated by a
        # blank line so the code block has blank lines around it.
        loose = any(any(not isinstance(c, List) for c in item.children) for item in self.children)
        sep = "\n\n" if loose else "\n"
        lines: list[str] = []
        for idx, item in enumerate(self.children, start=1):
            marker = f"{idx}." if self.ordered else "-"
            lines.append(_render_list_item(item, marker=marker))
        return sep.join(lines)


class Section(PromptNode):
    node_type: Literal[NodeType.Section] = NodeType.Section
    level: int = Field(ge=1, le=6)
    text: StrippedNonBlankStr
    children: list[SectionChild] = Field(default_factory=list)

    def to_markdown(self) -> str:
        head = "#" * self.level + " " + self.text
        return _join_blocks([head, *(c.to_markdown() for c in self.children)])


class Document(PromptNode):
    node_type: Literal[NodeType.Document] = NodeType.Document
    children: list[SectionChild] = Field(default_factory=list)

    def to_markdown(self) -> str:
        # MD047: files end with exactly one trailing newline.
        body = _join_blocks([c.to_markdown() for c in self.children])
        return body + "\n" if body else ""


BlockChild = Annotated[
    Paragraph | List | CodeBlock | Blockquote | Table,
    Field(discriminator="node_type"),
]

SectionChild = Annotated[
    Section | Paragraph | List | CodeBlock | Blockquote | Table,
    Field(discriminator="node_type"),
]

Node = Annotated[
    Document | Section | List | ListItem | Paragraph | CodeBlock | Blockquote | Table,
    Field(discriminator="node_type"),
]


def _render_list_item(item: ListItem, marker: str) -> str:
    prefix = marker + " "
    cont = " " * len(prefix)

    # Annotations and non-list block children are separated from the item
    # text (and from each other) by a blank line. Nested Lists hug the
    # preceding content with no blank line, matching the CommonMark tight form.
    body = item.text
    if item.example is not None:
        body += "\n\n" + item.example.to_markdown()
    if item.guidance is not None:
        body += "\n\n" + item.guidance.to_markdown()
    for child in item.children:
        if isinstance(child, List):
            body += "\n" + child.to_markdown()
        else:
            body += "\n\n" + child.to_markdown()

    first, _, rest = body.partition("\n")
    if not rest:
        return prefix + first
    return prefix + first + "\n" + _indent(rest, cont)


ListItem.model_rebuild()
Section.model_rebuild()
Document.model_rebuild()
