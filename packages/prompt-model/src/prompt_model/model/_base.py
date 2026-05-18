from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class NodeType(StrEnum):
    Document = "Document"
    Section = "Section"
    List = "List"
    ListItem = "ListItem"
    Paragraph = "Paragraph"
    CodeBlock = "CodeBlock"
    Blockquote = "Blockquote"
    Table = "Table"
    ExampleAnnotation = "ExampleAnnotation"
    GuidanceAnnotation = "GuidanceAnnotation"


class PromptNode(BaseModel):
    """Common base for every element in the prompt model tree.

    Subclasses redeclare `node_type` with a `Literal[...]` and override
    `to_markdown` to emit their canonical markdown form.
    """

    id: str | None = None
    node_type: NodeType

    def to_markdown(self) -> str:
        raise NotImplementedError(f"{type(self).__name__}.to_markdown not implemented")
