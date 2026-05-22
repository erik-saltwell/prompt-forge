from __future__ import annotations

from prompt_model._actor._redaction import DefaultRedactionStrategy
from prompt_model._prompt.parsing.parse_prompt import parse_from_string


def test_default_strategy_returns_full_content_for_document_sentinel() -> None:
    tree = parse_from_string("# alpha\n\nbody one\n\n# beta\n\nbody two\n")
    rendered = DefaultRedactionStrategy().render(tree, "document")

    assert "alpha" in rendered
    assert "beta" in rendered
    assert "body one" in rendered
    assert "body two" in rendered


def test_default_strategy_keeps_target_siblings_ancestors_elides_others() -> None:
    md = """# alpha

intro text

- li one
- li two

# beta

body two
"""
    tree = parse_from_string(md)
    # Find the paragraph "intro text"; structure is Document > Section(alpha)=1 > Paragraph(intro)=1.1, List=1.2
    rendered = DefaultRedactionStrategy().render(tree, "1.1")

    # Target paragraph content visible
    assert "intro text" in rendered
    # Ancestor section heading visible
    assert "alpha" in rendered
    # Sibling list and its items rendered structurally; sibling content visible per the rule
    # (siblings of paragraph 1.1 = the list 1.2)
    # Other root section's heading visible (headings always visible)
    assert "beta" in rendered
    # Other root section's body NOT visible
    assert "body two" not in rendered


def test_default_strategy_annotation_target_keeps_sibling_annotations() -> None:
    md = """intro

::: examples
- alpha example
- beta example
- gamma example
:::
"""
    tree = parse_from_string(md)
    # Paragraph 1 hosts an examples group with three annotations 1.e1, 1.e2, 1.e3.
    # Target is 1.e2 — its sibling annotations 1.e1 and 1.e3 must keep content.
    rendered = DefaultRedactionStrategy().render(tree, "1.e2")

    assert "beta example" in rendered
    assert "alpha example" in rendered
    assert "gamma example" in rendered
