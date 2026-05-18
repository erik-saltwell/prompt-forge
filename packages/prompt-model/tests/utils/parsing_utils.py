from __future__ import annotations

from prompt_model.model import (
    Blockquote,
    CodeBlock,
    Document,
    ExampleAnnotation,
    GuidanceAnnotation,
    List,
    ListItem,
    Paragraph,
    Section,
    SectionChild,
    Table,
)
from prompt_model.service.parsing.parse_prompt import parse_from_string


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


def structural_equal(a: object, b: object) -> bool:
    """Recursive tree equality that ignores `id` fields on nodes and annotations."""
    if type(a) is not type(b):
        return False

    if isinstance(a, Document):
        assert isinstance(b, Document)
        return _children_equal(a.children, b.children)

    if isinstance(a, Section):
        assert isinstance(b, Section)
        return a.level == b.level and a.text == b.text and _children_equal(a.children, b.children)

    if isinstance(a, List):
        assert isinstance(b, List)
        return a.ordered == b.ordered and _children_equal(a.children, b.children)

    if isinstance(a, ListItem):
        assert isinstance(b, ListItem)
        return (
            a.text == b.text
            and _annotations_equal(a.example, b.example)
            and _annotations_equal(a.guidance, b.guidance)
            and _children_equal(a.children, b.children)
        )

    if isinstance(a, Paragraph):
        assert isinstance(b, Paragraph)
        return a.text == b.text and _annotations_equal(a.example, b.example) and _annotations_equal(a.guidance, b.guidance)

    if isinstance(a, CodeBlock):
        assert isinstance(b, CodeBlock)
        return a.text == b.text and a.info == b.info

    if isinstance(a, (Blockquote, Table)):
        assert isinstance(b, (Blockquote, Table))
        return a.text == b.text

    return False


def assert_parses_to_shorthand(markdown_text: str, expected: str) -> None:
    tree = parse_from_string(markdown_text)
    assert_tree_matches_shorthand(tree, expected)


def assert_tree_matches_shorthand(tree: Document, expected: str) -> None:
    actual = tree_to_shorthand(tree)
    assert actual == expected, f"shorthand mismatch:\n  expected: {expected!r}\n  actual:   {actual!r}"


def assert_trees_structurally_equal(a: Document, b: Document) -> None:
    assert structural_equal(a, b), "trees are not structurally equal"


def doc_from_shorthand(shorthand: str) -> Document:
    """Build a Document from a shorthand token stream.

    Token texts are deterministic functions of token position so that two
    calls with the same shorthand produce structurally-equal trees.

    Grammar (mirrors tree_to_shorthand):
        h1..h6   Section at that heading level
        p        Paragraph
        cb       CodeBlock
        bq       Blockquote
        t        Table
        ul<N>    bullet list item at depth N (lists are inferred from runs)
        ol<N>    ordered list item at depth N
        e        ExampleAnnotation on the most recent Paragraph/ListItem
        g        GuidanceAnnotation on the most recent Paragraph/ListItem
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
            last_host.example = ExampleAnnotation(text=f"example-{idx}")
        elif tok == "g":
            if last_host is None:
                raise ValueError(f"shorthand token 'g' at index {idx}: no host")
            last_host.guidance = GuidanceAnnotation(text=f"guidance-{idx}")
        else:
            raise ValueError(f"unknown shorthand token {tok!r} at index {idx}")

    return doc


# --- internal helpers ---


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
        _emit_annotations(node.example, node.guidance, tokens)
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
        _emit_annotations(item.example, item.guidance, tokens)
        for child in item.children:
            if isinstance(child, List):
                _emit_list(child, depth + 1, tokens)
            # Non-list block children are out of scope for shorthand; skip silently.


def _emit_annotations(
    example: ExampleAnnotation | None,
    guidance: GuidanceAnnotation | None,
    tokens: list[str],
) -> None:
    if example is not None:
        tokens.append("e")
    if guidance is not None:
        tokens.append("g")


def _children_equal(a: list, b: list) -> bool:
    if len(a) != len(b):
        return False
    return all(structural_equal(x, y) for x, y in zip(a, b, strict=True))


def _annotations_equal(
    a: ExampleAnnotation | GuidanceAnnotation | None,
    b: ExampleAnnotation | GuidanceAnnotation | None,
) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return type(a) is type(b) and a.text == b.text
