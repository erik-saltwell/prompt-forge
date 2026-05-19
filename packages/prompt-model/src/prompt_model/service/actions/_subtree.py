from __future__ import annotations

from typing import Annotated

from pydantic import Field, TypeAdapter, ValidationError

from ...model import (
    Blockquote,
    CodeBlock,
    List,
    ListItem,
    Paragraph,
    PromptNode,
    Section,
    Table,
)

_InsertableNode = Annotated[
    Section | List | ListItem | Paragraph | CodeBlock | Blockquote | Table,
    Field(discriminator="node_type"),
]

_ADAPTER: TypeAdapter[_InsertableNode] = TypeAdapter(_InsertableNode)


def build_subtree(
    raw: object,
) -> Section | List | ListItem | Paragraph | CodeBlock | Blockquote | Table | None:
    """Materialise an insert_node payload into a PromptNode.

    Accepts either:
    - a bare string → `Paragraph(text=...)` (shorthand for the common case)
    - a dict matching the Pydantic discriminated union (`node_type` key)

    Returns None if the payload is neither shape, or if Pydantic rejects it
    (wrong type, missing required field, invalid structure)."""
    if isinstance(raw, str):
        if not raw.strip():
            return None
        try:
            return Paragraph(text=raw)
        except ValidationError:
            return None
    if isinstance(raw, dict):
        try:
            node = _ADAPTER.validate_python(raw)
        except ValidationError:
            return None
        if _has_empty_container(node):
            return None
        return node
    return None


def _has_empty_container(node: PromptNode) -> bool:
    """Containers (Section, List) must carry contents — per insert_node
    contract. ListItem has its own `text` so an item with no body children
    is still meaningful and is allowed."""
    if isinstance(node, (Section, List)) and not node.children:
        return True
    children = getattr(node, "children", None) or ()
    return any(_has_empty_container(c) for c in children)
