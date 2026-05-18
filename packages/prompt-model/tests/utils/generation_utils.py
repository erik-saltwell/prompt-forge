from __future__ import annotations

from prompt_model.model import PromptNode
from prompt_model.service.parsing.parse_prompt import parse_from_string

from tests.utils.parsing_utils import (
    doc_from_shorthand,
    tree_to_shorthand,
)

from .parsing_utils import (
    assert_tree_matches_shorthand,
    assert_trees_structurally_equal,
)


def assert_renders_to(node: PromptNode, expected: str) -> None:
    """Assert that node.to_markdown() exactly equals `expected`."""
    actual = node.to_markdown()
    assert actual == expected, f"to_markdown mismatch:\n--- expected ---\n{expected}\n--- actual ---\n{actual}"


def assert_markdown_renders_to(markdown: str, expected: str) -> None:
    """Parse `markdown`, render the resulting Document, compare to `expected`."""
    assert_renders_to(parse_from_string(markdown), expected)


def assert_render_matches_shorthand(markdown: str, shorthand: str) -> None:
    """Parse `markdown` -> render -> re-parse -> compare shorthand."""
    tree = parse_from_string(markdown)
    regenerated = tree.to_markdown()
    reparsed = parse_from_string(regenerated)
    assert_tree_matches_shorthand(reparsed, shorthand)


def assert_markdown_roundtrips(markdown: str) -> None:
    """Parse -> render -> parse -> render and assert stable.

    Checks two invariants:
    - Re-parsing the generated markdown yields a tree structurally equal to
      the first parse (ID-ignoring).
    - Rendering that re-parsed tree yields the same canonical markdown as
      the first render (idempotence of `to_markdown` after a roundtrip).
    """
    tree_a = parse_from_string(markdown)
    md_a = tree_a.to_markdown()

    tree_b = parse_from_string(md_a)
    md_b = tree_b.to_markdown()

    assert_trees_structurally_equal(tree_a, tree_b)
    assert md_a == md_b, f"second render differs from first:\n--- first ---\n{md_a}\n--- second ---\n{md_b}"


def assert_shorthand_roundtrips(expected_shorthand: str) -> None:
    doc = doc_from_shorthand(expected_shorthand)
    markdown: str = doc.to_markdown()
    reparsed = parse_from_string(markdown)
    actual_shorthand = tree_to_shorthand(reparsed)
    assert actual_shorthand == expected_shorthand, (
        f"shorthand round-trip mismatch:\n  expected: {expected_shorthand!r}\n  actual:   {actual_shorthand!r}"
    )
    assert_trees_structurally_equal(doc, reparsed)
