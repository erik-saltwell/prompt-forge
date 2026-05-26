from __future__ import annotations

from typing import ClassVar
from xml.sax.saxutils import escape, quoteattr

from ..._prompt import Document
from ..._prompt.annotations import Annotation, ExamplesGroup, GuidanceGroup
from ..._prompt.nodes import Blockquote, CodeBlock, List, ListItem, Paragraph, Section, Table
from ._resources import load_rendering_resource

ELIDED: str = "…"


class XmlRenderPromptStrategy:
    """Renders the tree as XML with `id` attributes on every addressable node."""

    format_snippet_resource: ClassVar[str] = "xml"

    def describe_format(self) -> str:
        return load_rendering_resource(self.format_snippet_resource)

    def render(self, tree: Document, focus_ids: set[str] | None) -> str:
        return _to_xml(tree, focus_ids=focus_ids)


def _to_xml(tree: Document, focus_ids: set[str] | None) -> str:
    lines: list[str] = ["<document>"]
    for child in tree.children:
        lines.append(_xml_render(child, focus_ids, "  "))
    lines.append("</document>")
    return "\n".join(lines)


def _xml_txt(node_id: str, text: str, focus_ids: set[str] | None) -> str:
    if focus_ids is None or node_id in focus_ids:
        return escape(text)
    return ELIDED


def _xml_render(node: object, focus_ids: set[str] | None, indent: str) -> str:
    if isinstance(node, Section):
        attrs = f'id={quoteattr(node.id or "")} level="{node.level}" heading={quoteattr(_xml_txt(node.id or "", node.text, focus_ids))}'
        if not node.children:
            return f"{indent}<section {attrs}/>"
        inner = "\n".join(_xml_render(c, focus_ids, indent + "  ") for c in node.children)
        return f"{indent}<section {attrs}>\n{inner}\n{indent}</section>"
    if isinstance(node, Paragraph):
        body = _xml_txt(node.id or "", node.text, focus_ids)
        annos: list[str] = []
        if node.examples is not None:
            annos.append(_xml_render_group(node.examples, "examples", focus_ids, indent + "  "))
        if node.guidance is not None:
            annos.append(_xml_render_group(node.guidance, "guidance", focus_ids, indent + "  "))
        if annos:
            return f"{indent}<paragraph id={quoteattr(node.id or '')}>{body}\n" + "\n".join(annos) + f"\n{indent}</paragraph>"
        return f"{indent}<paragraph id={quoteattr(node.id or '')}>{body}</paragraph>"
    if isinstance(node, List):
        attrs = f'id={quoteattr(node.id or "")} ordered="{"true" if node.ordered else "false"}"'
        if not node.children:
            return f"{indent}<list {attrs}/>"
        inner = "\n".join(_xml_render(c, focus_ids, indent + "  ") for c in node.children)
        return f"{indent}<list {attrs}>\n{inner}\n{indent}</list>"
    if isinstance(node, ListItem):
        body = _xml_txt(node.id or "", node.text, focus_ids)
        item_annos: list[str] = []
        if node.examples is not None:
            item_annos.append(_xml_render_group(node.examples, "examples", focus_ids, indent + "  "))
        if node.guidance is not None:
            item_annos.append(_xml_render_group(node.guidance, "guidance", focus_ids, indent + "  "))
        children_inner = "\n".join(_xml_render(c, focus_ids, indent + "  ") for c in node.children)
        bits: list[str] = []
        if item_annos:
            bits.append("\n".join(item_annos))
        if children_inner:
            bits.append(children_inner)
        if bits:
            return f"{indent}<item id={quoteattr(node.id or '')}>{body}\n" + "\n".join(bits) + f"\n{indent}</item>"
        return f"{indent}<item id={quoteattr(node.id or '')}>{body}</item>"
    if isinstance(node, CodeBlock):
        info_attr = f" info={quoteattr(node.info)}" if node.info else ""
        return f"{indent}<code id={quoteattr(node.id or '')}{info_attr}>{_xml_txt(node.id or '', node.text, focus_ids)}</code>"
    if isinstance(node, Blockquote):
        return f"{indent}<blockquote id={quoteattr(node.id or '')}>{_xml_txt(node.id or '', node.text, focus_ids)}</blockquote>"
    if isinstance(node, Table):
        return f"{indent}<table id={quoteattr(node.id or '')}>{_xml_txt(node.id or '', node.text, focus_ids)}</table>"
    return f"{indent}<!-- unhandled: {type(node).__name__} -->"


def _xml_render_group(group: ExamplesGroup | GuidanceGroup, tag: str, focus_ids: set[str] | None, indent: str) -> str:
    if not group.children:
        return f"{indent}<{tag}/>"
    inner = "\n".join(_xml_render_annotation(a, focus_ids, indent + "  ") for a in group.children)
    return f"{indent}<{tag}>\n{inner}\n{indent}</{tag}>"


def _xml_render_annotation(ann: Annotation, focus_ids: set[str] | None, indent: str) -> str:
    return f"{indent}<annotation id={quoteattr(ann.id or '')}>{_xml_txt(ann.id or '', ann.text, focus_ids)}</annotation>"
