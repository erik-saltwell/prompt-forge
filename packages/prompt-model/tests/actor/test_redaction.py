from __future__ import annotations

from prompt_model._prompt import Document
from prompt_model._prompt.parsing.parse_prompt import parse_from_string
from prompt_model.strategies.prompt_rendering_strategy import XmlRenderPromptStrategy
from prompt_model.strategies.redaction_strategy import ContextualRedactionStrategy


def _render(tree: Document, culprit_id: str) -> str:
    focus = ContextualRedactionStrategy().focus_ids(tree, culprit_id)
    return XmlRenderPromptStrategy().render(tree, focus)


def test_default_strategy_returns_full_content_for_document_sentinel() -> None:
    tree = parse_from_string("# alpha\n\nbody one\n\n# beta\n\nbody two\n")
    rendered = _render(tree, "document")

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
    rendered = _render(tree, "1.1")

    assert "intro text" in rendered
    assert "alpha" in rendered
    assert "beta" in rendered
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
    rendered = _render(tree, "1.e2")

    assert "beta example" in rendered
    assert "alpha example" in rendered
    assert "gamma example" in rendered
