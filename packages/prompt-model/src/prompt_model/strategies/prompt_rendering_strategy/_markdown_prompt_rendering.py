from __future__ import annotations

from typing import ClassVar

from ..._prompt import Document
from ..._prompt.annotations import ExamplesGroup, GuidanceGroup
from ..._prompt.nodes import Blockquote, CodeBlock, List, ListItem, Paragraph, Section, Table
from ._resources import load_rendering_resource

ELIDED: str = "…"


class MarkdownRenderPromptStrategy:
    """Conforming markdown interleaved with `<!-- id -->` HTML comments."""

    format_snippet_resource: ClassVar[str] = "markdown"

    def describe_format(self) -> str:
        return load_rendering_resource(self.format_snippet_resource)

    def render(self, tree: Document, focus_ids: set[str] | None) -> str:
        return render_prompt_to_markdown(tree, focus_ids=focus_ids)


def render_prompt_to_markdown(tree: Document, focus_ids: set[str] | None = None) -> str:
    """Render the prompt as conforming markdown with `<!-- id -->` HTML comments.

    When `focus_ids` is `None`, all content renders verbatim. Otherwise, any
    addressable node whose id is not in the set has its text replaced by the
    elision marker. Structural syntax is preserved.
    """
    parts: list[str] = [_markdown_render_block(c, focus_ids) for c in tree.children]
    body: str = _join_markdown_blocks(parts)
    return body + "\n" if body else ""


def _markdown_render_block(node: object, focus_ids: set[str] | None) -> str:
    if isinstance(node, Section):
        return _markdown_section(node, focus_ids)
    if isinstance(node, Paragraph):
        return _markdown_paragraph(node, focus_ids)
    if isinstance(node, List):
        return _markdown_list(node, focus_ids)
    if isinstance(node, CodeBlock):
        return _markdown_code(node, focus_ids)
    if isinstance(node, Blockquote):
        return _markdown_blockquote(node, focus_ids)
    if isinstance(node, Table):
        return _markdown_table(node, focus_ids)
    return ""


def _markdown_section(node: Section, focus_ids: set[str] | None) -> str:
    heading: str = "#" * node.level + " " + _markdown_txt(node.id, node.text, focus_ids)
    head: str = f"<!-- {node.id} -->\n{heading}"
    if not node.children:
        return head
    children_md: str = _join_markdown_blocks([_markdown_render_block(c, focus_ids) for c in node.children])
    return head + "\n\n" + children_md


def _markdown_paragraph(node: Paragraph, focus_ids: set[str] | None) -> str:
    body: str = _markdown_txt(node.id, node.text, focus_ids)
    head: str = f"<!-- {node.id} -->\n{body}"
    extras: list[str] = []
    if node.examples is not None:
        extras.append(_markdown_group(node.examples, focus_ids))
    if node.guidance is not None:
        extras.append(_markdown_group(node.guidance, focus_ids))
    if extras:
        return head + "\n\n" + "\n\n".join(extras)
    return head


def _markdown_list(node: List, focus_ids: set[str] | None) -> str:
    head: str = f"<!-- {node.id} -->"
    loose: bool = any(any(not isinstance(c, List) for c in item.children) for item in node.children)
    sep: str = "\n\n" if loose else "\n"
    items: list[str] = []
    for idx, item in enumerate(node.children, start=1):
        marker: str = f"{idx}." if node.ordered else "-"
        items.append(_markdown_list_item(item, marker, focus_ids))
    return head + "\n" + sep.join(items)


def _markdown_list_item(item: ListItem, marker: str, focus_ids: set[str] | None) -> str:
    prefix: str = marker + " "
    cont: str = " " * len(prefix)
    body: str = _markdown_txt(item.id, item.text, focus_ids)
    if item.examples is not None:
        body += "\n" + _markdown_group(item.examples, focus_ids)
    if item.guidance is not None:
        body += "\n" + _markdown_group(item.guidance, focus_ids)
    for child in item.children:
        if isinstance(child, List):
            body += "\n" + _markdown_render_block(child, focus_ids)
        else:
            body += "\n\n" + _markdown_render_block(child, focus_ids)
    head_line: str = prefix + f"<!-- {item.id} -->"
    first, _, rest = body.partition("\n")
    body_block: str = cont + first
    if rest:
        body_block += "\n" + _indent_markdown(rest, cont)
    return head_line + "\n" + body_block


def _markdown_code(node: CodeBlock, focus_ids: set[str] | None) -> str:
    body: str = _markdown_txt(node.id, node.text, focus_ids).rstrip("\n")
    return f"<!-- {node.id} -->\n```{node.info}\n{body}\n```"


def _markdown_blockquote(node: Blockquote, focus_ids: set[str] | None) -> str:
    body: str = _markdown_txt(node.id, node.text, focus_ids)
    quoted: str = "\n".join(f"> {line}" if line else ">" for line in body.split("\n"))
    return f"<!-- {node.id} -->\n{quoted}"


def _markdown_table(node: Table, focus_ids: set[str] | None) -> str:
    body: str = _markdown_txt(node.id, node.text, focus_ids)
    return f"<!-- {node.id} -->\n{body}"


def _markdown_group(group: ExamplesGroup | GuidanceGroup, focus_ids: set[str] | None) -> str:
    label: str = "examples" if isinstance(group, ExamplesGroup) else "guidance"
    children = group.children
    if len(children) == 1:
        ann = children[0]
        body: str = _markdown_txt(ann.id, ann.text, focus_ids).rstrip("\n")
        return f"<!-- {ann.id} -->\n::: {label}\n{body}\n:::"
    lines: list[str] = [f"::: {label}"]
    for ann in children:
        ann_body: str = _markdown_txt(ann.id, ann.text, focus_ids)
        first, _, rest = ann_body.partition("\n")
        line: str = f"- <!-- {ann.id} -->\n  {first}"
        if rest:
            line += "\n" + _indent_markdown(rest, "  ")
        lines.append(line)
    lines.append(":::")
    return "\n".join(lines)


def _markdown_txt(node_id: str | None, text: str, focus_ids: set[str] | None) -> str:
    if focus_ids is None or (isinstance(node_id, str) and node_id in focus_ids):
        return text
    return ELIDED


def _indent_markdown(text: str, prefix: str) -> str:
    return "\n".join(prefix + line if line else "" for line in text.split("\n"))


def _join_markdown_blocks(parts: list[str]) -> str:
    return "\n\n".join(p for p in parts if p)
