from __future__ import annotations

from ._json_prompt_rendering import JsonRenderPromptStrategy
from ._markdown_prompt_rendering import MarkdownRenderPromptStrategy
from ._xml_prompt_rendering import XmlRenderPromptStrategy
from .prompt_rendering_options import RenderPromptOption
from .prompt_rendering_protocol import RenderPromptStrategy


def make_prompt_render_strategy(option: RenderPromptOption) -> RenderPromptStrategy:  # type: ignore[return]
    """Return a ``RenderPromptStrategy`` instance for *option*."""

    match option:
        case RenderPromptOption.XML:
            return XmlRenderPromptStrategy()
        case RenderPromptOption.JSON:
            return JsonRenderPromptStrategy()
        case RenderPromptOption.MARKDOWN:
            return MarkdownRenderPromptStrategy()
    raise ValueError(f"Unsupported prompt render strategy: {option!r}")
