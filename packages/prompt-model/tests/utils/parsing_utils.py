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
