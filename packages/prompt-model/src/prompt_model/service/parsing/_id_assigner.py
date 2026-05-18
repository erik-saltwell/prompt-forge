from __future__ import annotations

from ...model import (
    Blockquote,
    CodeBlock,
    Document,
    List,
    ListItem,
    Paragraph,
    Section,
    Table,
)

_IdentifiableNode = Section | List | ListItem | Paragraph | CodeBlock | Blockquote | Table


def assign_ids(doc: Document) -> None:
    for i, child in enumerate(doc.children, start=1):
        _assign(child, str(i))


def _assign(node: _IdentifiableNode, node_id: str) -> None:
    node.id = node_id

    if isinstance(node, (Paragraph, ListItem)):
        if node.example is not None:
            node.example.id = f"{node_id}.e1"
        if node.guidance is not None:
            node.guidance.id = f"{node_id}.g1"

    children = getattr(node, "children", None)
    if children:
        for i, child in enumerate(children, start=1):
            _assign(child, f"{node_id}.{i}")
