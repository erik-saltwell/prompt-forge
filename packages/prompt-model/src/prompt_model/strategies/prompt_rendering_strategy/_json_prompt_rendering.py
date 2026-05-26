from __future__ import annotations

import json
from typing import ClassVar, cast

from ..._prompt import Document
from ._resources import load_rendering_resource

ELIDED: str = "…"


class JsonRenderPromptStrategy:
    """Renders the tree as JSON via Pydantic's `model_dump`.

    When `focus_ids` is provided, the `text` field of any node whose `id`
    is not in the set is replaced by the elision marker. Structural fields
    (`level`, `ordered`, `info`, `node_type`, `id`) are always preserved.
    """

    format_snippet_resource: ClassVar[str] = "json"

    def describe_format(self) -> str:
        return load_rendering_resource(self.format_snippet_resource)

    def render(self, tree: Document, focus_ids: set[str] | None) -> str:
        data: object = tree.model_dump(mode="json")
        if focus_ids is not None:
            _elide(data, focus_ids)
        return json.dumps(data, indent=2, ensure_ascii=False)


def _elide(node: object, focus_ids: set[str]) -> None:
    if isinstance(node, dict):
        node_dict: dict[str, object] = cast(dict[str, object], node)
        node_id: object = node_dict.get("id")
        if isinstance(node_id, str) and node_id not in focus_ids and "text" in node_dict:
            node_dict["text"] = ELIDED
        for v in node_dict.values():
            _elide(v, focus_ids)
    elif isinstance(node, list):
        for item in node:
            _elide(item, focus_ids)
