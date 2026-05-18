from __future__ import annotations

from typing import Final

from markdown_it.tree import SyntaxTreeNode

from ...model import (
    Blockquote,
    CodeBlock,
    Document,
    ExampleAnnotation,
    GuidanceAnnotation,
    List,
    ListItem,
    Paragraph,
    Section,
    Table,
)

_ANNOTATION_TYPES: Final[frozenset[str]] = frozenset({"container_example", "container_examples", "container_guidance"})


def build_document(root: SyntaxTreeNode) -> Document:
    doc = Document()
    section_stack: list[Section] = []
    current_host: Paragraph | ListItem | None = None

    def container() -> Document | Section:
        return section_stack[-1] if section_stack else doc

    for tn in root.children:
        if tn.type == "heading":
            level = int(tn.tag[1:])
            while section_stack and section_stack[-1].level >= level:
                section_stack.pop()
            section = Section(level=level, text=_inline_text(tn))
            container().children.append(section)
            section_stack.append(section)
            current_host = None
        elif _is_annotation(tn):
            _attach_annotation(current_host, tn)
        else:
            block = _build_block(tn)
            container().children.append(block)
            current_host = block if isinstance(block, Paragraph) else None

    return doc


def _build_block(tn: SyntaxTreeNode) -> Paragraph | List | CodeBlock | Blockquote | Table:
    if tn.type == "paragraph":
        return Paragraph(text=_inline_text(tn))
    if tn.type in ("bullet_list", "ordered_list"):
        ordered = tn.type == "ordered_list"
        return List(
            ordered=ordered,
            children=[_build_list_item(child) for child in tn.children],
        )
    if tn.type == "fence":
        return CodeBlock(text=tn.content, info=tn.info or "")
    if tn.type == "code_block":
        return CodeBlock(text=tn.content, info="")
    if tn.type == "blockquote":
        return Blockquote(text=_flatten_text(tn))
    if tn.type == "table":
        return Table(text=_flatten_text(tn))
    raise ValueError(f"unsupported block token type: {tn.type}")


def _build_list_item(tn: SyntaxTreeNode) -> ListItem:
    children = list(tn.children)
    text = ""
    rest_start = 0
    if children and children[0].type == "paragraph":
        text = _inline_text(children[0])
        rest_start = 1

    item = ListItem(text=text)
    current_host: Paragraph | ListItem | None = item

    for ctn in children[rest_start:]:
        if _is_annotation(ctn):
            _attach_annotation(current_host, ctn)
            continue
        block = _build_block(ctn)
        item.children.append(block)
        current_host = block if isinstance(block, Paragraph) else None

    return item


def _is_annotation(tn: SyntaxTreeNode) -> bool:
    return tn.type in _ANNOTATION_TYPES


def _attach_annotation(host: Paragraph | ListItem | None, tn: SyntaxTreeNode) -> None:
    if host is None:
        return
    body = _flatten_text(tn).strip()
    if not body:
        return
    if tn.type == "container_guidance":
        host.guidance = GuidanceAnnotation(text=body)
    else:
        host.example = ExampleAnnotation(text=body)


def _inline_text(tn: SyntaxTreeNode) -> str:
    """Return the raw source of a heading or paragraph's inline content.

    Inline markup (bold, italic, links, code spans) is preserved as literal
    text — it is not a separate node in the model, but it is part of the
    text the author wrote and may carry semantic emphasis for the LLM.
    """
    for child in tn.children:
        if child.type == "inline":
            return child.content
    return ""


def _flatten_text(tn: SyntaxTreeNode) -> str:
    """Collapse a subtree to text, joining each inline run with newlines.

    Inline markup is preserved (each `inline.content` is raw source). Used
    for blockquotes, tables, and annotation bodies — block structure is
    flattened, inline markup is kept.
    """
    parts: list[str] = []

    def walk(node: SyntaxTreeNode) -> None:
        if node.type == "inline":
            parts.append(node.content)
            return
        for child in node.children:
            walk(child)

    walk(tn)
    return "\n".join(parts)
