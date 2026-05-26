from __future__ import annotations

from .._prompt.annotations import ExamplesGroup, GuidanceGroup
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


def to_critic_markdown(tree: Document, focus_ids: set[str] | None = None) -> str:
    """Render the document as conforming markdown interleaved with `<!-- id -->`
    HTML comments per `prompt-serialization.md`.

    When `focus_ids` is `None`, all content renders verbatim. Otherwise, any
    addressable node whose id is not in the set has its text replaced by the
    elision marker. Structural syntax (heading hashes, list markers, code-fence
    info, annotation directives) is preserved.
    """
    parts: list[str] = [_render_block(c, focus_ids) for c in tree.children]
    body: str = _join_blocks(parts)
    return body + "\n" if body else ""


def _render_block(node: object, focus_ids: set[str] | None) -> str:
    if isinstance(node, Section):
        return _section(node, focus_ids)
    if isinstance(node, Paragraph):
        return _paragraph(node, focus_ids)
    if isinstance(node, List):
        return _list(node, focus_ids)
    if isinstance(node, CodeBlock):
        return _code(node, focus_ids)
    if isinstance(node, Blockquote):
        return _blockquote(node, focus_ids)
    if isinstance(node, Table):
        return _table(node, focus_ids)
    return ""


def _section(node: Section, focus_ids: set[str] | None) -> str:
    heading: str = "#" * node.level + " " + _txt(node.id, node.text, focus_ids)
    head: str = f"<!-- {node.id} -->\n{heading}"
    if not node.children:
        return head
    children_md: str = _join_blocks([_render_block(c, focus_ids) for c in node.children])
    return head + "\n\n" + children_md


def _paragraph(node: Paragraph, focus_ids: set[str] | None) -> str:
    body: str = _txt(node.id, node.text, focus_ids)
    head: str = f"<!-- {node.id} -->\n{body}"
    extras: list[str] = []
    if node.examples is not None:
        extras.append(_group(node.examples, focus_ids))
    if node.guidance is not None:
        extras.append(_group(node.guidance, focus_ids))
    if extras:
        return head + "\n\n" + "\n\n".join(extras)
    return head


def _list(node: List, focus_ids: set[str] | None) -> str:
    head: str = f"<!-- {node.id} -->"
    loose: bool = any(any(not isinstance(c, List) for c in item.children) for item in node.children)
    sep: str = "\n\n" if loose else "\n"
    items: list[str] = []
    for idx, item in enumerate(node.children, start=1):
        marker: str = f"{idx}." if node.ordered else "-"
        items.append(_list_item(item, marker, focus_ids))
    return head + "\n" + sep.join(items)


def _list_item(item: ListItem, marker: str, focus_ids: set[str] | None) -> str:
    prefix: str = marker + " "
    cont: str = " " * len(prefix)
    body: str = _txt(item.id, item.text, focus_ids)
    if item.examples is not None:
        body += "\n" + _group(item.examples, focus_ids)
    if item.guidance is not None:
        body += "\n" + _group(item.guidance, focus_ids)
    for child in item.children:
        if isinstance(child, List):
            body += "\n" + _render_block(child, focus_ids)
        else:
            body += "\n\n" + _render_block(child, focus_ids)
    head_line: str = prefix + f"<!-- {item.id} -->"
    first, _, rest = body.partition("\n")
    body_block: str = cont + first
    if rest:
        body_block += "\n" + _indent(rest, cont)
    return head_line + "\n" + body_block


def _code(node: CodeBlock, focus_ids: set[str] | None) -> str:
    body: str = _txt(node.id, node.text, focus_ids).rstrip("\n")
    return f"<!-- {node.id} -->\n```{node.info}\n{body}\n```"


def _blockquote(node: Blockquote, focus_ids: set[str] | None) -> str:
    body: str = _txt(node.id, node.text, focus_ids)
    quoted: str = "\n".join(f"> {line}" if line else ">" for line in body.split("\n"))
    return f"<!-- {node.id} -->\n{quoted}"


def _table(node: Table, focus_ids: set[str] | None) -> str:
    body: str = _txt(node.id, node.text, focus_ids)
    return f"<!-- {node.id} -->\n{body}"


def _group(group: ExamplesGroup | GuidanceGroup, focus_ids: set[str] | None) -> str:
    label: str = "examples" if isinstance(group, ExamplesGroup) else "guidance"
    children = group.children
    if len(children) == 1:
        ann = children[0]
        body: str = _txt(ann.id, ann.text, focus_ids).rstrip("\n")
        return f"<!-- {ann.id} -->\n::: {label}\n{body}\n:::"
    lines: list[str] = [f"::: {label}"]
    for ann in children:
        ann_body: str = _txt(ann.id, ann.text, focus_ids)
        first, _, rest = ann_body.partition("\n")
        line: str = f"- <!-- {ann.id} -->\n  {first}"
        if rest:
            line += "\n" + _indent(rest, "  ")
        lines.append(line)
    lines.append(":::")
    return "\n".join(lines)


def _txt(node_id: str | None, text: str, focus_ids: set[str] | None) -> str:
    if focus_ids is None or (isinstance(node_id, str) and node_id in focus_ids):
        return text
    return ELIDED


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line if line else "" for line in text.split("\n"))


def _join_blocks(parts: list[str]) -> str:
    return "\n\n".join(p for p in parts if p)
