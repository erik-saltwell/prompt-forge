from __future__ import annotations

from prompt_model.model import (
    Document,
    PromptNode,
)
from prompt_model.service.parsing.parse_prompt import parse_from_string

from ._short_hand import tree_to_shorthand
from ._tree_comparison import structural_equal


def check_md_against_sh(markdown_text: str, shorthand: str) -> None:
    tree = parse_from_string(markdown_text)
    check_obj_against_sh(tree, shorthand)


def check_obj_against_sh(tree: Document, expected: str) -> None:
    actual = tree_to_shorthand(tree)
    assert actual == expected, f"shorthand mismatch:\n  expected: {expected!r}\n  actual:   {actual!r}"


def check_obj_against_obj(a: Document, b: Document) -> None:
    assert structural_equal(a, b), "trees are not structurally equal"


def check_obj_against_md(node: PromptNode, expected: str) -> None:
    """Assert that node.to_markdown() exactly equals `expected`."""
    actual = node.to_markdown()
    assert actual == expected, f"to_markdown mismatch:\n--- expected ---\n{expected}\n--- actual ---\n{actual}"


def check_md_against_md(markdown: str, expected: str) -> None:
    """Parse `markdown`, render the resulting Document, compare to `expected`."""
    check_obj_against_md(parse_from_string(markdown), expected)
