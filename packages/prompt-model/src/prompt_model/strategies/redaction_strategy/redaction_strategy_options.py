from __future__ import annotations

from enum import StrEnum


class RedactionOption(StrEnum):
    """Selects which redaction strategy the actor uses when rendering the tree for the feedback LLM.

    The strategy controls how much of the prompt tree is shown verbatim versus elided when the
    actor focuses on a specific culprit node.
    """

    CONTEXTUAL = "contextual"
    """Show the culprit, its ancestors, its siblings, and all section headings; elide everything else."""

    NONE = "none"
    """Show the entire tree verbatim — no elision. Useful for benchmarking and debugging."""
