from __future__ import annotations

from ._contextual_redaction_strategy import ContextualRedactionStrategy
from ._no_redaction_strategy import NoRedactionStrategy
from .redaction_strategy_options import RedactionOption
from .redaction_strategy_protocol import RedactionStrategy


def make_redaction_strategy(option: RedactionOption) -> RedactionStrategy:  # type: ignore[return]
    """Return a ``RedactionStrategy`` instance for *option*."""

    match option:
        case RedactionOption.CONTEXTUAL:
            return ContextualRedactionStrategy()
        case RedactionOption.NONE:
            return NoRedactionStrategy()
    raise ValueError(f"Unsupported redaction strategy: {option!r}")
