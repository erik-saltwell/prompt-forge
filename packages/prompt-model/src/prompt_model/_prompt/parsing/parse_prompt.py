from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode
from mdit_py_plugins.container import container_plugin

from .. import Document
from ._id_assigner import assign_ids
from ._tree_builder import build_document


def _build_parser() -> MarkdownIt:
    parser = MarkdownIt("commonmark").enable("table")
    for name in ("example", "examples", "guidance"):
        parser = parser.use(container_plugin, name)
    return parser


_PARSER = _build_parser()


def parse_from_string(markdown_text: str) -> Document:
    tokens = _PARSER.parse(markdown_text)
    root = SyntaxTreeNode(tokens)
    doc = build_document(root, markdown_text)
    assign_ids(doc)
    return doc


def parse_from_file(filepath: Path) -> Document:
    if not filepath.exists():
        raise FileNotFoundError(filepath)
    if not filepath.is_file():
        raise IsADirectoryError(filepath)
    return parse_from_string(filepath.read_text())
