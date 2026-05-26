from __future__ import annotations

import json
from typing import ClassVar, Protocol, cast
from xml.sax.saxutils import escape, quoteattr

from .._prompt import Document
from .._prompt.annotations import Annotation, ExamplesGroup, GuidanceGroup
from .._prompt.nodes import (
    Blockquote,
    CodeBlock,
    List,
    ListItem,
    Paragraph,
    Section,
    Table,
)
from ._critic_markdown import to_critic_markdown
from ._resources import load_rendering_resource

ELIDED: str = "…"


class RenderPromptStrategy(Protocol):
    """Renders a Document as the string the LLM will read, and describes its
    own rendering convention via `describe_format()`.

    `focus_ids = None` means render every node's content verbatim.
    Otherwise, nodes whose id is in the set keep their content; everything
    else is replaced by an elision marker. Structure and IDs always render.

    `describe_format()` returns the markdown snippet a system prompt embeds
    to teach the LLM how to read the rendered output and how to cite node
    IDs back in its JSON response.
    """

    def render(self, tree: Document, focus_ids: set[str] | None) -> str: ...

    def describe_format(self) -> str: ...


class _ResourceFormatDescription:
    """Mixin: `describe_format()` loads `format_snippet_resource` from
    `_resources/prompt_format/<name>.md`. Subclasses set the ClassVar.
    """

    format_snippet_resource: ClassVar[str]

    def describe_format(self) -> str:
        return load_rendering_resource("prompt_format", self.format_snippet_resource)


class XmlRenderPromptStrategy(_ResourceFormatDescription):
    """Renders the tree as XML with `id` attributes on every addressable node."""

    format_snippet_resource: ClassVar[str] = "xml"

    def render(self, tree: Document, focus_ids: set[str] | None) -> str:
        return _to_xml(tree, focus_ids=focus_ids)


class JsonRenderPromptStrategy(_ResourceFormatDescription):
    """Renders the tree as JSON via Pydantic's `model_dump`.

    When `focus_ids` is provided, the `text` field of any node whose `id`
    is not in the set is replaced by the elision marker. Structural fields
    (`level`, `ordered`, `info`, `node_type`, `id`) are always preserved.
    """

    format_snippet_resource: ClassVar[str] = "json"

    def render(self, tree: Document, focus_ids: set[str] | None) -> str:
        data: object = tree.model_dump(mode="json")
        if focus_ids is not None:
            _elide(data, focus_ids)
        return json.dumps(data, indent=2, ensure_ascii=False)


class MarkdownRenderPromptStrategy(_ResourceFormatDescription):
    """Critic-form: conforming markdown interleaved with `<!-- id -->` HTML
    comments per `prompt-serialization.md`.
    """

    format_snippet_resource: ClassVar[str] = "markdown"

    def render(self, tree: Document, focus_ids: set[str] | None) -> str:
        return to_critic_markdown(tree, focus_ids=focus_ids)


# --- JSON helpers ---


def _elide(node: object, focus_ids: set[str]) -> None:
    if isinstance(node, dict):
        node_dict: dict[str, object] = cast(dict[str, object], node)
        node_id: object = node_dict.get("id")
        if isinstance(node_id, str) and node_id not in focus_ids and "text" in node_dict:
            node_dict["text"] = ELIDED
        for v in node_dict.values():
            _elide(v, focus_ids)
    elif isinstance(node, list):
        for item in node:
            _elide(item, focus_ids)


# --- XML helpers ---


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
