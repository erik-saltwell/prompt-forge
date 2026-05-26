from __future__ import annotations

from enum import StrEnum


class RenderPromptOption(StrEnum):
    """Selects the serialization format the actor LLM reads the prompt tree in."""

    XML = "xml"
    """XML with ``id`` attributes on every addressable node. Default and recommended for Claude models."""

    JSON = "json"
    """Pydantic ``model_dump`` JSON. Non-focus node text is replaced with the elision marker."""

    MARKDOWN = "markdown"
    """Critic-form conforming markdown interleaved with ``<!-- id -->`` HTML comments."""
