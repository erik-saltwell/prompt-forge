from __future__ import annotations

from ._json_signal_rendering import JsonSignalRenderingStrategy
from ._markdown_signal_rendering import MarkdownSignalRenderingStrategy
from ._xml_signal_rendering import XmlSignalRenderingStrategy
from .signal_render_options import RenderSignalOption
from .signal_rendering_protocol import SignalRenderingStrategy


def make_signal_render_strategy(option: RenderSignalOption) -> SignalRenderingStrategy:  # type: ignore[return]
    """Return a ``SignalRenderingStrategy`` instance for *option*."""
    match option:
        case RenderSignalOption.MARKDOWN:
            return MarkdownSignalRenderingStrategy()
        case RenderSignalOption.JSON:
            return JsonSignalRenderingStrategy()
        case RenderSignalOption.XML:
            return XmlSignalRenderingStrategy()
    raise ValueError(f"Unsupported signal render strategy: {option!r}")
