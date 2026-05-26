from __future__ import annotations

from enum import StrEnum


class RenderSignalOption(StrEnum):
    """Selects how the aggregated issue signals bucket is formatted in the actor's user prompt."""

    MARKDOWN = "markdown"
    """Humanized ``## Issue N`` markdown subsections with labeled fields. Default."""

    JSON = "json"
    """Pretty-printed JSON via Pydantic."""

    XML = "xml"
    """``<signal>`` elements with field sub-elements. Mirrors XML prompt rendering for structural consistency."""
