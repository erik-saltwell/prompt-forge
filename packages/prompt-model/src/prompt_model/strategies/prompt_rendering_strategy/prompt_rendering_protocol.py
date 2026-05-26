from __future__ import annotations

from typing import Protocol

from ..._prompt import Document


class RenderPromptStrategy(Protocol):
    """Renders a Document as the string the LLM will read, and describes its
    own rendering convention via `describe_format()`.

    `focus_ids = None` means render every node's content verbatim.
    Otherwise, nodes whose id is in the set keep their content; everything
    else is replaced by an elision marker. Structure and IDs always render.

    `describe_format()` returns the markdown snippet a system prompt embeds
    to teach the LLM how to read the rendered output and how to cite node
    IDs back in its JSON response.
    """

    def render(self, tree: Document, focus_ids: set[str] | None) -> str: ...

    def describe_format(self) -> str: ...
