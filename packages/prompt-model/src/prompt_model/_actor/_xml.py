from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr

from .._prompt.annotations import Annotation, ExamplesGroup, GuidanceGroup
from .._prompt.nodes import (
    Blockquote,
    CodeBlock,
    Document,
    List,
    ListItem,
    Paragraph,
    Section,
    Table,
)

ELIDED: str = "…"


def to_xml(tree: Document, focus_ids: set[str] | None = None) -> str:
    """Render the document as XML.

    `focus_ids = None` shows every node's content. When provided, only nodes
    whose `id` is in the set show their actual text; others render with an
    elision marker. Structure and IDs are always rendered.
    """
    lines: list[str] = ["<document>"]
    for child in tree.children:
        lines.append(_render(child, focus_ids, "  "))
    lines.append("</document>")
    return "\n".join(lines)


def _txt(node_id: str, text: str, focus_ids: set[str] | None) -> str:
    if focus_ids is None or node_id in focus_ids:
        return escape(text)
    return ELIDED


def _render(node: object, focus_ids: set[str] | None, indent: str) -> str:
    if isinstance(node, Section):
        attrs = f'id={quoteattr(node.id or "")} level="{node.level}" heading={quoteattr(_txt(node.id or "", node.text, focus_ids))}'
        if not node.children:
            return f"{indent}<section {attrs}/>"
        inner = "\n".join(_render(c, focus_ids, indent + "  ") for c in node.children)
        return f"{indent}<section {attrs}>\n{inner}\n{indent}</section>"
    if isinstance(node, Paragraph):
        body = _txt(node.id or "", node.text, focus_ids)
        annos: list[str] = []
        if node.examples is not None:
            annos.append(_render_group(node.examples, "examples", focus_ids, indent + "  "))
        if node.guidance is not None:
            annos.append(_render_group(node.guidance, "guidance", focus_ids, indent + "  "))
        if annos:
            return f"{indent}<paragraph id={quoteattr(node.id or '')}>{body}\n" + "\n".join(annos) + f"\n{indent}</paragraph>"
        return f"{indent}<paragraph id={quoteattr(node.id or '')}>{body}</paragraph>"
    if isinstance(node, List):
        attrs = f'id={quoteattr(node.id or "")} ordered="{"true" if node.ordered else "false"}"'
        if not node.children:
            return f"{indent}<list {attrs}/>"
        inner = "\n".join(_render(c, focus_ids, indent + "  ") for c in node.children)
        return f"{indent}<list {attrs}>\n{inner}\n{indent}</list>"
    if isinstance(node, ListItem):
        body = _txt(node.id or "", node.text, focus_ids)
        annos = []
        if node.examples is not None:
            annos.append(_render_group(node.examples, "examples", focus_ids, indent + "  "))
        if node.guidance is not None:
            annos.append(_render_group(node.guidance, "guidance", focus_ids, indent + "  "))
        children_inner = "\n".join(_render(c, focus_ids, indent + "  ") for c in node.children)
        bits: list[str] = []
        if annos:
            bits.append("\n".join(annos))
        if children_inner:
            bits.append(children_inner)
        if bits:
            return f"{indent}<item id={quoteattr(node.id or '')}>{body}\n" + "\n".join(bits) + f"\n{indent}</item>"
        return f"{indent}<item id={quoteattr(node.id or '')}>{body}</item>"
    if isinstance(node, CodeBlock):
        info_attr = f" info={quoteattr(node.info)}" if node.info else ""
        return f"{indent}<code id={quoteattr(node.id or '')}{info_attr}>{_txt(node.id or '', node.text, focus_ids)}</code>"
    if isinstance(node, Blockquote):
        return f"{indent}<blockquote id={quoteattr(node.id or '')}>{_txt(node.id or '', node.text, focus_ids)}</blockquote>"
    if isinstance(node, Table):
        return f"{indent}<table id={quoteattr(node.id or '')}>{_txt(node.id or '', node.text, focus_ids)}</table>"
    return f"{indent}<!-- unhandled: {type(node).__name__} -->"


def _render_group(group: ExamplesGroup | GuidanceGroup, tag: str, focus_ids: set[str] | None, indent: str) -> str:
    if not group.children:
        return f"{indent}<{tag}/>"
    inner = "\n".join(_render_annotation(a, focus_ids, indent + "  ") for a in group.children)
    return f"{indent}<{tag}>\n{inner}\n{indent}</{tag}>"


def _render_annotation(ann: Annotation, focus_ids: set[str] | None, indent: str) -> str:
    return f"{indent}<annotation id={quoteattr(ann.id or '')}>{_txt(ann.id or '', ann.text, focus_ids)}</annotation>"
