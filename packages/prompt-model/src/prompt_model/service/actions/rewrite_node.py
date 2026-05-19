from __future__ import annotations

import re

from ..._protocols.action import Action, ApplyContext, SkipReason
from ...model import (
    Blockquote,
    CodeBlock,
    Document,
    ListItem,
    Paragraph,
    Section,
    Table,
)
from ._walk import find_node_by_id
from .registry import register

_RewritableNode = Section | Paragraph | ListItem | CodeBlock | Blockquote | Table

# Leading ATX heading markers on a Section's text are stripped (and any
# surrounding whitespace collapsed) — actor LLMs frequently emit "## Foo"
# as the new heading text; the level lives on the node itself.
_LEADING_HASHES_RE = re.compile(r"^\s*#{1,6}\s+")


class RewriteNodeAction:
    """Replace the text of a node. Text-only; node type and structural
    properties (Section.level, List.ordered, CodeBlock.info) are untouched."""

    def __init__(self, node_id: str, text: str) -> None:
        self.node_id = node_id
        self.text = text

    def _resolve(self, tree: Document) -> _RewritableNode | None:
        node = find_node_by_id(tree, self.node_id)
        if isinstance(node, (Section, Paragraph, ListItem, CodeBlock, Blockquote, Table)):
            return node
        return None

    def _normalised_text(self, node: _RewritableNode) -> str:
        if isinstance(node, Section):
            return _LEADING_HASHES_RE.sub("", self.text, count=1)
        return self.text

    def _validate_text(self, node: _RewritableNode) -> SkipReason | None:
        text = self._normalised_text(node)
        if not text.strip():
            return SkipReason.InvalidContent
        if isinstance(node, Section):
            if "\n" in text:
                return SkipReason.InvalidContent
        if isinstance(node, (Paragraph, ListItem, Blockquote)):
            if ":::" in text:
                return SkipReason.InvalidContent
        if isinstance(node, CodeBlock):
            if "```" in text or ":::" in text:
                return SkipReason.InvalidContent
        if isinstance(node, Table):
            if "|" not in text:
                return SkipReason.InvalidContent
        return None

    def validate(self, tree: Document) -> SkipReason | None:
        node = self._resolve(tree)
        if node is None:
            return SkipReason.TargetNotFound
        return self._validate_text(node)

    def apply(self, tree: Document, ctx: ApplyContext | None = None) -> Action:
        node = self._resolve(tree)
        assert node is not None, "apply() called without a successful validate()"
        old_text = node.text
        node.text = self._normalised_text(node)
        return RewriteNodeAction(self.node_id, old_text)


@register("rewrite_node")
def _build_rewrite_node(raw: dict) -> Action | SkipReason:
    node_id = raw.get("id")
    text = raw.get("text")
    if not isinstance(node_id, str) or not node_id:
        return SkipReason.MissingRequired
    if not isinstance(text, str) or not text.strip():
        return SkipReason.MissingRequired
    return RewriteNodeAction(node_id, text)
