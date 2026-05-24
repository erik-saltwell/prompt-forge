from __future__ import annotations

import json

from prompt_model._actor._redaction import DefaultRedactionStrategy
from prompt_model._actor._render_prompt_strategy import JsonRenderPromptStrategy, MarkdownRenderPromptStrategy
from prompt_model._prompt.parsing.parse_prompt import parse_from_string


def test_json_full_render_preserves_all_content() -> None:
    tree = parse_from_string("# alpha\n\nbody one\n\n# beta\n\nbody two\n")
    rendered: str = JsonRenderPromptStrategy().render(tree, None)

    data = json.loads(rendered)
    assert data["children"][0]["text"] == "alpha"
    assert data["children"][0]["children"][0]["text"] == "body one"
    assert data["children"][1]["text"] == "beta"
    assert data["children"][1]["children"][0]["text"] == "body two"


def test_json_focused_render_elides_text_outside_focus() -> None:
    tree = parse_from_string("# alpha\n\nbody one\n\n# beta\n\nbody two\n")
    focus = DefaultRedactionStrategy().focus_ids(tree, "1.1")
    rendered: str = JsonRenderPromptStrategy().render(tree, focus)

    data = json.loads(rendered)
    # focused paragraph keeps content
    assert data["children"][0]["children"][0]["text"] == "body one"
    # other section's paragraph body is elided; its heading stays (sections always in focus)
    assert data["children"][1]["text"] == "beta"
    assert data["children"][1]["children"][0]["text"] == "…"


def test_json_preserves_structural_fields() -> None:
    tree = parse_from_string("# alpha\n\n- one\n- two\n")
    focus = DefaultRedactionStrategy().focus_ids(tree, "1.1.1")
    rendered: str = JsonRenderPromptStrategy().render(tree, focus)

    data = json.loads(rendered)
    list_node = data["children"][0]["children"][0]
    assert list_node["node_type"] == "List"
    assert "ordered" in list_node
    assert list_node["id"] == "1.1"


def test_json_output_is_valid_json() -> None:
    tree = parse_from_string("intro\n\n::: examples\n- alpha\n- beta\n:::\n")
    rendered: str = JsonRenderPromptStrategy().render(tree, None)
    json.loads(rendered)  # raises if invalid


# --- MarkdownRenderPromptStrategy (critic form) ---


def test_md_full_render_emits_id_comment_for_every_addressable_node() -> None:
    tree = parse_from_string("# alpha\n\nintro\n\n- one\n- two\n")
    rendered: str = MarkdownRenderPromptStrategy().render(tree, None)

    for node_id in ["1", "1.1", "1.2", "1.2.1", "1.2.2"]:
        assert f"<!-- {node_id} -->" in rendered


def test_md_focused_render_elides_text_outside_focus() -> None:
    tree = parse_from_string("# alpha\n\nbody one\n\n# beta\n\nbody two\n")
    focus = DefaultRedactionStrategy().focus_ids(tree, "1.1")
    rendered: str = MarkdownRenderPromptStrategy().render(tree, focus)

    assert "body one" in rendered  # in focus
    assert "body two" not in rendered  # out of focus
    assert "…" in rendered  # elided
    assert "alpha" in rendered  # section headings always in focus
    assert "beta" in rendered


def test_md_list_item_comment_appears_after_marker() -> None:
    tree = parse_from_string("- one\n- two\n")
    rendered: str = MarkdownRenderPromptStrategy().render(tree, None)

    # List item id comment is inline after the bullet marker.
    assert "- <!-- 1.1 -->\n  one" in rendered
    assert "- <!-- 1.2 -->\n  two" in rendered


def test_md_annotation_list_form_emits_comment_after_bullet() -> None:
    md = "intro\n\n::: examples\n- alpha\n- beta\n:::\n"
    tree = parse_from_string(md)
    rendered: str = MarkdownRenderPromptStrategy().render(tree, None)

    assert "::: examples" in rendered
    assert "- <!-- 1.e1 -->\n  alpha" in rendered
    assert "- <!-- 1.e2 -->\n  beta" in rendered
    assert ":::" in rendered


def test_md_annotation_text_form_emits_comment_before_directive() -> None:
    md = "intro\n\n::: guidance\nbe concise\n:::\n"
    tree = parse_from_string(md)
    rendered: str = MarkdownRenderPromptStrategy().render(tree, None)

    # Text-form annotation: comment goes BEFORE the ::: opening line.
    assert "<!-- 1.g1 -->\n::: guidance\nbe concise\n:::" in rendered


def test_md_preserves_structural_syntax_under_elision() -> None:
    tree = parse_from_string("## sub\n\nbody\n")
    rendered: str = MarkdownRenderPromptStrategy().render(tree, set())  # everything elided

    # heading hash preserved even though text elided
    assert "## …" in rendered
    # body elided
    assert "body" not in rendered
