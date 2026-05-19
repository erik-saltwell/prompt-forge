from __future__ import annotations

from typing import Final

from markdown_it.tree import SyntaxTreeNode

from ...model import (
    Annotation,
    Blockquote,
    CodeBlock,
    Document,
    ExamplesGroup,
    GuidanceGroup,
    List,
    ListItem,
    Paragraph,
    Section,
    Table,
)

_ANNOTATION_TYPES: Final[frozenset[str]] = frozenset({"container_example", "container_examples", "container_guidance"})


def build_document(root: SyntaxTreeNode, source: str) -> Document:
    source_lines = source.split("\n")
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
            block = _build_block(tn, source_lines)
            container().children.append(block)
            current_host = block if isinstance(block, Paragraph) else None

    return doc


def _build_block(tn: SyntaxTreeNode, source_lines: list[str]) -> Paragraph | List | CodeBlock | Blockquote | Table:
    if tn.type == "paragraph":
        return Paragraph(text=_inline_text(tn))
    if tn.type in ("bullet_list", "ordered_list"):
        ordered = tn.type == "ordered_list"
        return List(
            ordered=ordered,
            children=[_build_list_item(child, source_lines) for child in tn.children],
        )
    if tn.type == "fence":
        return CodeBlock(text=tn.content, info=tn.info or "")
    if tn.type == "code_block":
        return CodeBlock(text=tn.content, info="")
    if tn.type == "blockquote":
        return Blockquote(text=_flatten_text(tn))
    if tn.type == "table":
        # Preserve the original markdown source slice so the table roundtrips
        # through to_markdown(). markdown-it's `.map` is `[start, end)` in lines.
        if tn.map is None:
            raise ValueError("table token is missing source map")
        start, end = tn.map
        return Table(text="\n".join(source_lines[start:end]))
    raise ValueError(f"unsupported block token type: {tn.type}")


def _build_list_item(tn: SyntaxTreeNode, source_lines: list[str]) -> ListItem:
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
        block = _build_block(ctn, source_lines)
        item.children.append(block)
        current_host = block if isinstance(block, Paragraph) else None

    return item


def _is_annotation(tn: SyntaxTreeNode) -> bool:
    return tn.type in _ANNOTATION_TYPES


def _attach_annotation(host: Paragraph | ListItem | None, tn: SyntaxTreeNode) -> None:
    if host is None:
        return
    annotations = _extract_annotations(tn)
    if not annotations:
        return

    if tn.type == "container_guidance":
        if host.guidance is None:
            host.guidance = GuidanceGroup(children=annotations)
        else:
            host.guidance.children.extend(annotations)
    else:
        if host.examples is None:
            host.examples = ExamplesGroup(children=annotations)
        else:
            host.examples.children.extend(annotations)


def _extract_annotations(tn: SyntaxTreeNode) -> list[Annotation]:
    """Build the list of Annotations from a directive container.

    Two valid forms (per the spec):
    - One or more paragraphs → ONE annotation, paragraphs joined by `\n`.
    - A single flat bullet list → ONE annotation per list item.

    Anything else is a validation error; the parser is best-effort here so
    downstream code sees a well-shaped tree even when validation rejects.
    Preference order: bullet list (if any) → paragraphs.
    """
    bullet_lists = [c for c in tn.children if c.type == "bullet_list"]
    if bullet_lists:
        return _annotations_from_bullet_list(bullet_lists[0])

    paragraphs = [c for c in tn.children if c.type == "paragraph"]
    if paragraphs:
        body = "\n".join(_inline_text(p) for p in paragraphs).strip()
        if body:
            return [Annotation(text=body)]
    return []


def _annotations_from_bullet_list(tn: SyntaxTreeNode) -> list[Annotation]:
    out: list[Annotation] = []
    for li in tn.children:
        text_parts: list[str] = []
        for child in li.children:
            if child.type == "paragraph":
                text_parts.append(_inline_text(child))
        body = "\n".join(text_parts).strip()
        if body:
            out.append(Annotation(text=body))
    return out


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
    for blockquotes — block structure is flattened, inline markup is kept.
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
