from __future__ import annotations

from typing import Annotated

from pydantic import Field, TypeAdapter, ValidationError

from ...model import (
    Blockquote,
    CodeBlock,
    Document,
    List,
    ListItem,
    Paragraph,
    PromptNode,
    Section,
    Table,
)
from ..parsing.parse_prompt import parse_from_string
from ._walk import has_empty_container

_InsertableNode = Annotated[
    Section | List | ListItem | Paragraph | CodeBlock | Blockquote | Table,
    Field(discriminator="node_type"),
]

_ADAPTER: TypeAdapter[_InsertableNode] = TypeAdapter(_InsertableNode)


def build_subtrees(raw: object) -> list[PromptNode] | None:
    """Materialise an insert_node payload into one or more root PromptNodes.

    Accepts either:
    - a markdown string — parsed via the standard `parse_from_string`
      pipeline; the resulting `Document.children` become the roots (a multi-
      block string splats into multiple roots).
    - a dict matching the Pydantic discriminated union (`node_type` key) —
      yields a single root.

    Returns None if the payload is neither shape, parses to nothing, or
    contains an empty Section/List (which cannot be reserialised to
    conforming markdown). Pydantic validation errors also return None."""
    if isinstance(raw, str):
        if not raw.strip():
            return None
        try:
            doc: Document = parse_from_string(raw)
        except Exception:
            return None
        roots: list[PromptNode] = list(doc.children)
        if not roots:
            return None
        if any(has_empty_container(r) for r in roots):
            return None
        return roots
    if isinstance(raw, dict):
        try:
            node = _ADAPTER.validate_python(raw)
        except ValidationError:
            return None
        if has_empty_container(node):
            return None
        return [node]
    return None
