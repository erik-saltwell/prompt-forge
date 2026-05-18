from __future__ import annotations

from prompt_model.service.parsing.parse_prompt import parse_from_string

from ._short_hand import doc_from_shorthand, tree_to_shorthand
from .parsing import check_obj_against_obj, check_obj_against_sh


def md_obj_md_obj_md(markdown: str) -> None:
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

    check_obj_against_obj(tree_a, tree_b)
    assert md_a == md_b, f"second render differs from first:\n--- first ---\n{md_a}\n--- second ---\n{md_b}"


def sh_obj_md_obj_sh(expected_shorthand: str) -> None:
    doc = doc_from_shorthand(expected_shorthand)
    markdown: str = doc.to_markdown()
    reparsed = parse_from_string(markdown)
    actual_shorthand = tree_to_shorthand(reparsed)
    assert actual_shorthand == expected_shorthand, (
        f"shorthand round-trip mismatch:\n  expected: {expected_shorthand!r}\n  actual:   {actual_shorthand!r}"
    )
    check_obj_against_obj(doc, reparsed)
    check_obj_against_sh(reparsed, expected_shorthand)
