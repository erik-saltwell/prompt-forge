from __future__ import annotations

from prompt_model.prompt import (
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


def _children_equal(a: list, b: list) -> bool:
    if len(a) != len(b):
        return False
    return all(structural_equal(x, y) for x, y in zip(a, b, strict=True))


def _groups_equal(
    a: ExamplesGroup | GuidanceGroup | None,
    b: ExamplesGroup | GuidanceGroup | None,
) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if type(a) is not type(b):
        return False
    if len(a.children) != len(b.children):
        return False
    return all(_annotation_equal(x, y) for x, y in zip(a.children, b.children, strict=True))


def _annotation_equal(a: Annotation, b: Annotation) -> bool:
    return a.text == b.text


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
            and _groups_equal(a.examples, b.examples)
            and _groups_equal(a.guidance, b.guidance)
            and _children_equal(a.children, b.children)
        )

    if isinstance(a, Paragraph):
        assert isinstance(b, Paragraph)
        return a.text == b.text and _groups_equal(a.examples, b.examples) and _groups_equal(a.guidance, b.guidance)

    if isinstance(a, CodeBlock):
        assert isinstance(b, CodeBlock)
        return a.text == b.text and a.info == b.info

    if isinstance(a, (Blockquote, Table)):
        assert isinstance(b, (Blockquote, Table))
        return a.text == b.text

    return False
