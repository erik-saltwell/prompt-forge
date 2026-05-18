from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .._utils.pydantic_aliases import StrippedNonBlankStr
from .annotations import ExampleAnnotation, GuidanceAnnotation


class NodeType(StrEnum):
    Document = "Document"
    Section = "Section"
    List = "List"
    ListItem = "ListItem"
    Paragraph = "Paragraph"
    CodeBlock = "CodeBlock"
    Blockquote = "Blockquote"
    Table = "Table"


class Paragraph(BaseModel):
    node_type: Literal[NodeType.Paragraph] = NodeType.Paragraph
    id: str | None = None
    text: StrippedNonBlankStr
    example: ExampleAnnotation | None = None
    guidance: GuidanceAnnotation | None = None


class CodeBlock(BaseModel):
    node_type: Literal[NodeType.CodeBlock] = NodeType.CodeBlock
    id: str | None = None
    text: str = ""
    info: str = ""


class Blockquote(BaseModel):
    node_type: Literal[NodeType.Blockquote] = NodeType.Blockquote
    id: str | None = None
    text: str = ""


class Table(BaseModel):
    node_type: Literal[NodeType.Table] = NodeType.Table
    id: str | None = None
    text: str = ""


class ListItem(BaseModel):
    node_type: Literal[NodeType.ListItem] = NodeType.ListItem
    id: str | None = None
    text: StrippedNonBlankStr
    children: list[BlockChild] = Field(default_factory=list)
    example: ExampleAnnotation | None = None
    guidance: GuidanceAnnotation | None = None


class List(BaseModel):
    node_type: Literal[NodeType.List] = NodeType.List
    id: str | None = None
    ordered: bool
    children: list[ListItem] = Field(default_factory=list)


class Section(BaseModel):
    node_type: Literal[NodeType.Section] = NodeType.Section
    id: str | None = None
    level: int = Field(ge=1, le=6)
    text: StrippedNonBlankStr
    children: list[SectionChild] = Field(default_factory=list)


class Document(BaseModel):
    node_type: Literal[NodeType.Document] = NodeType.Document
    children: list[SectionChild] = Field(default_factory=list)


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

ListItem.model_rebuild()
Section.model_rebuild()
Document.model_rebuild()
