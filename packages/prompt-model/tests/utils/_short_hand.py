"""Shorthand <-> object and shorthand -> markdown conversions.

The shorthand grammar:
    h1..h6   Section at that heading level
    p        Paragraph
    cb       CodeBlock
    bq       Blockquote
    t        Table
    ul<N>    bullet list item at depth N (lists inferred from runs)
    ol<N>    ordered list item at depth N
    e        Append one Annotation to the most recent Paragraph/ListItem's
             ExamplesGroup (creating the group on first occurrence)
    g        Append one Annotation to the most recent Paragraph/ListItem's
             GuidanceGroup (creating the group on first occurrence)

`shorthand_to_markdown` is an independent reimplementation that does not call
into any product code under `src/`. Its output is markdownlint-compliant.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from prompt_model.model import (
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
    SectionChild,
    Table,
)
from prompt_model.service.parsing._id_assigner import assign_ids


@dataclass
class _SectionBlock:
    level: int
    text: str
    children: list[_Block] = field(default_factory=list)


@dataclass
class _ParagraphBlock:
    text: str
    examples: list[str] = field(default_factory=list)
    guidance: list[str] = field(default_factory=list)


@dataclass
class _CodeBlockDict:
    text: str
    info: str = ""


@dataclass
class _BlockquoteBlock:
    text: str


@dataclass
class _TableBlock:
    idx: int


@dataclass
class _ListBlock:
    ordered: bool
    children: list[_ItemBlock] = field(default_factory=list)


@dataclass
class _ItemBlock:
    text: str
    children: list[_Block] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    guidance: list[str] = field(default_factory=list)


type _Block = _SectionBlock | _ParagraphBlock | _CodeBlockDict | _BlockquoteBlock | _TableBlock | _ListBlock
type _HostBlock = _ParagraphBlock | _ItemBlock

# ---------------------------------------------------------------------------
# tree -> shorthand
# ---------------------------------------------------------------------------


def tree_to_shorthand(tree: Document) -> str:
    """Render a parsed tree as a flat shorthand token stream.

    Nesting is implicit: section depth comes from heading levels, list
    nesting comes from the depth suffix on `ul<N>`/`ol<N>`. ListItem
    block children other than nested Lists are silently skipped — they
    are out of scope for shorthand by design; tests that need to assert
    them must use exact-file comparison instead.
    """
    tokens: list[str] = []
    for child in tree.children:
        _emit_section_child(child, tokens)
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# shorthand -> tree
# ---------------------------------------------------------------------------


def doc_from_shorthand(shorthand: str) -> Document:
    """Build a Document from a shorthand token stream.

    Token texts are deterministic functions of token position so that two
    calls with the same shorthand produce structurally-equal trees.
    """
    doc = Document()
    section_stack: list[Section] = []
    list_stack: list[List] = []
    last_host: Paragraph | ListItem | None = None

    def container_children() -> list[SectionChild]:
        return section_stack[-1].children if section_stack else doc.children

    for idx, tok in enumerate(shorthand.split()):
        if len(tok) == 2 and tok[0] == "h" and tok[1].isdigit():
            level = int(tok[1])
            list_stack.clear()
            while section_stack and section_stack[-1].level >= level:
                section_stack.pop()
            section = Section(level=level, text=f"section-{idx}")
            container_children().append(section)
            section_stack.append(section)
            last_host = None
        elif tok == "p":
            list_stack.clear()
            para = Paragraph(text=f"paragraph-{idx}")
            container_children().append(para)
            last_host = para
        elif tok == "cb":
            list_stack.clear()
            container_children().append(CodeBlock(text=f"code-{idx}\n", info=""))
            last_host = None
        elif tok == "bq":
            list_stack.clear()
            container_children().append(Blockquote(text=f"blockquote-{idx}"))
            last_host = None
        elif tok == "t":
            list_stack.clear()
            container_children().append(Table(text=f"table-{idx}"))
            last_host = None
        elif (tok.startswith("ul") or tok.startswith("ol")) and tok[2:].isdigit():
            ordered = tok.startswith("ol")
            depth = int(tok[2:])
            if depth < 1:
                raise ValueError(f"shorthand token {tok!r} at index {idx}: depth must be >= 1")
            while len(list_stack) > depth:
                list_stack.pop()
            if len(list_stack) == depth and list_stack[-1].ordered != ordered:
                list_stack.pop()
            if len(list_stack) < depth:
                if len(list_stack) != depth - 1:
                    raise ValueError(f"shorthand token {tok!r} at index {idx}: skipped a list-depth level")
                new_list = List(ordered=ordered, children=[])
                if depth == 1:
                    container_children().append(new_list)
                else:
                    parent_list = list_stack[-1]
                    if not parent_list.children:
                        raise ValueError(f"shorthand token {tok!r} at index {idx}: nested list has no parent item")
                    parent_list.children[-1].children.append(new_list)
                list_stack.append(new_list)
            item = ListItem(text=f"item-{idx}", children=[])
            list_stack[-1].children.append(item)
            last_host = item
        elif tok == "e":
            if last_host is None:
                raise ValueError(f"shorthand token 'e' at index {idx}: no host")
            ann = Annotation(text=f"example-{idx}")
            if last_host.examples is None:
                last_host.examples = ExamplesGroup(children=[ann])
            else:
                last_host.examples.children.append(ann)
        elif tok == "g":
            if last_host is None:
                raise ValueError(f"shorthand token 'g' at index {idx}: no host")
            ann = Annotation(text=f"guidance-{idx}")
            if last_host.guidance is None:
                last_host.guidance = GuidanceGroup(children=[ann])
            else:
                last_host.guidance.children.append(ann)
        else:
            raise ValueError(f"unknown shorthand token {tok!r} at index {idx}")

    assign_ids(doc)
    return doc


# ---------------------------------------------------------------------------
# shorthand -> markdown (independent reimplementation; no product code)
# ---------------------------------------------------------------------------


def shorthand_to_markdown(shorthand: str) -> str:
    """Render shorthand directly to markdownlint-compliant markdown.

    Does not depend on the product model or its `to_markdown` methods.
    Produces canonical-form markdown: ATX headings with one space, dash
    bullet markers with two-space nested indent, ordered lists renumbered
    from 1, backtick fences, single trailing newline.
    """
    blocks: list[_Block] = []
    section_stack: list[_SectionBlock] = []
    list_stack: list[_ListBlock] = []
    last_host: _HostBlock | None = None

    def container() -> list[_Block]:
        return section_stack[-1].children if section_stack else blocks

    for idx, tok in enumerate(shorthand.split()):
        if len(tok) == 2 and tok[0] == "h" and tok[1].isdigit():
            level = int(tok[1])
            list_stack.clear()
            while section_stack and section_stack[-1].level >= level:
                section_stack.pop()
            section = _SectionBlock(level=level, text=f"section-{idx}")
            container().append(section)
            section_stack.append(section)
            last_host = None
        elif tok == "p":
            list_stack.clear()
            para = _ParagraphBlock(text=f"paragraph-{idx}")
            container().append(para)
            last_host = para
        elif tok == "cb":
            list_stack.clear()
            container().append(_CodeBlockDict(text=f"code-{idx}"))
            last_host = None
        elif tok == "bq":
            list_stack.clear()
            container().append(_BlockquoteBlock(text=f"blockquote-{idx}"))
            last_host = None
        elif tok == "t":
            list_stack.clear()
            container().append(_TableBlock(idx=idx))
            last_host = None
        elif (tok.startswith("ul") or tok.startswith("ol")) and tok[2:].isdigit():
            ordered = tok.startswith("ol")
            depth = int(tok[2:])
            if depth < 1:
                raise ValueError(f"shorthand token {tok!r} at index {idx}: depth must be >= 1")
            while len(list_stack) > depth:
                list_stack.pop()
            if len(list_stack) == depth and list_stack[-1].ordered != ordered:
                list_stack.pop()
            if len(list_stack) < depth:
                if len(list_stack) != depth - 1:
                    raise ValueError(f"shorthand token {tok!r} at index {idx}: skipped a list-depth level")
                new_list = _ListBlock(ordered=ordered)
                if depth == 1:
                    container().append(new_list)
                else:
                    parent_item = list_stack[-1].children[-1]
                    parent_item.children.append(new_list)
                list_stack.append(new_list)
            item = _ItemBlock(text=f"item-{idx}")
            list_stack[-1].children.append(item)
            last_host = item
        elif tok == "e":
            if last_host is None:
                raise ValueError(f"shorthand token 'e' at index {idx}: no host")
            last_host.examples.append(f"example-{idx}")
        elif tok == "g":
            if last_host is None:
                raise ValueError(f"shorthand token 'g' at index {idx}: no host")
            last_host.guidance.append(f"guidance-{idx}")
        else:
            raise ValueError(f"unknown shorthand token {tok!r} at index {idx}")

    body = _render_blocks(blocks)
    return body + "\n" if body else ""


# ---------------------------------------------------------------------------
# internal: tree -> shorthand helpers
# ---------------------------------------------------------------------------


def _emit_section_child(node: object, tokens: list[str]) -> None:
    if isinstance(node, Section):
        tokens.append(f"h{node.level}")
        for child in node.children:
            _emit_section_child(child, tokens)
    else:
        _emit_block(node, tokens)


def _emit_block(node: object, tokens: list[str]) -> None:
    if isinstance(node, Paragraph):
        tokens.append("p")
        _emit_annotations(node.examples, node.guidance, tokens)
    elif isinstance(node, CodeBlock):
        tokens.append("cb")
    elif isinstance(node, Blockquote):
        tokens.append("bq")
    elif isinstance(node, Table):
        tokens.append("t")
    elif isinstance(node, List):
        _emit_list(node, depth=1, tokens=tokens)


def _emit_list(node: List, depth: int, tokens: list[str]) -> None:
    prefix = "ol" if node.ordered else "ul"
    for item in node.children:
        tokens.append(f"{prefix}{depth}")
        _emit_annotations(item.examples, item.guidance, tokens)
        for child in item.children:
            if isinstance(child, List):
                _emit_list(child, depth + 1, tokens)
            # Non-list block children are out of scope for shorthand; skip silently.


def _emit_annotations(
    examples: ExamplesGroup | None,
    guidance: GuidanceGroup | None,
    tokens: list[str],
) -> None:
    if examples is not None:
        tokens.extend("e" for _ in examples.children)
    if guidance is not None:
        tokens.extend("g" for _ in guidance.children)


# ---------------------------------------------------------------------------
# internal: shorthand -> markdown rendering
# ---------------------------------------------------------------------------


def _render_blocks(blocks: list[_Block]) -> str:
    return "\n\n".join(p for p in (_render_block(b) for b in blocks) if p)


def _render_block(b: _Block) -> str:
    if isinstance(b, _SectionBlock):
        head = "#" * b.level + " " + b.text
        body = _render_blocks(b.children)
        return head + "\n\n" + body if body else head
    if isinstance(b, _ParagraphBlock):
        parts: list[str] = [b.text]
        if b.examples:
            parts.append(_directive("examples", b.examples))
        if b.guidance:
            parts.append(_directive("guidance", b.guidance))
        return "\n\n".join(parts)
    if isinstance(b, _CodeBlockDict):
        return f"```{b.info}\n{b.text}\n```"
    if isinstance(b, _BlockquoteBlock):
        return "\n".join(f"> {line}" if line else ">" for line in b.text.split("\n"))
    if isinstance(b, _TableBlock):
        return f"| col |\n| --- |\n| cell-{b.idx} |"
    if isinstance(b, _ListBlock):
        return _render_list(b)
    raise ValueError(f"unknown block: {b!r}")


def _directive(label: str, texts: list[str]) -> str:
    if len(texts) == 1:
        body = texts[0]
    else:
        body = "\n".join(f"- {t}" for t in texts)
    return f"::: {label}\n{body}\n:::"


def _render_list(lst: _ListBlock) -> str:
    loose = any(any(not isinstance(c, _ListBlock) for c in item.children) for item in lst.children)
    sep = "\n\n" if loose else "\n"
    parts: list[str] = []
    for idx, item in enumerate(lst.children, start=1):
        marker = f"{idx}." if lst.ordered else "-"
        parts.append(_render_item(item, marker))
    return sep.join(parts)


def _render_item(item: _ItemBlock, marker: str) -> str:
    prefix = marker + " "
    cont = " " * len(prefix)

    body = item.text
    if item.examples:
        body += "\n\n" + _directive("examples", item.examples)
    if item.guidance:
        body += "\n\n" + _directive("guidance", item.guidance)
    for child in item.children:
        if isinstance(child, _ListBlock):
            body += "\n" + _render_list(child)
        else:
            body += "\n\n" + _render_block(child)

    first, _, rest = body.partition("\n")
    if not rest:
        return prefix + first
    return prefix + first + "\n" + _indent(rest, cont)


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line if line else "" for line in text.split("\n"))
