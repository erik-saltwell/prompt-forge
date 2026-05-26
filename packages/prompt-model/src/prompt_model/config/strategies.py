from __future__ import annotations

from enum import StrEnum


class RedactionStrategyOption(StrEnum):
    """Selects which redaction strategy the actor uses when rendering the tree for the feedback LLM.

    The strategy controls how much of the prompt tree is shown verbatim versus elided when the
    actor focuses on a specific culprit node.
    """

    DEFAULT = "default"
    """Show the culprit, its ancestors, its siblings, and all section headings; elide everything else."""

    NONE = "none"
    """Show the entire tree verbatim — no elision. Useful for benchmarking and debugging."""


class PromptRenderStrategyOption(StrEnum):
    """Selects the serialization format the actor LLM reads the prompt tree in."""

    XML = "xml"
    """XML with ``id`` attributes on every addressable node. Default and recommended for Claude models."""

    JSON = "json"
    """Pydantic ``model_dump`` JSON. Non-focus node text is replaced with the elision marker."""

    MARKDOWN = "markdown"
    """Critic-form conforming markdown interleaved with ``<!-- id -->`` HTML comments."""


class SignalRenderStrategyOption(StrEnum):
    """Selects how the aggregated issue signals bucket is formatted in the actor's user prompt."""

    MARKDOWN = "markdown"
    """Humanized ``## Issue N`` markdown subsections with labeled fields. Default."""

    JSON = "json"
    """Pretty-printed JSON via Pydantic."""

    XML = "xml"
    """``<signal>`` elements with field sub-elements. Mirrors XML prompt rendering for structural consistency."""


class StructuralCleanupOption(StrEnum):
    """Selects when the optional structural cleanup LLM pass runs after the per-node feedback pass."""

    ALWAYS = "always"
    """Always run the structural cleanup pass. Default."""

    NEVER = "never"
    """Never run the structural cleanup pass. Saves one LLM call per bucket."""

    ON_STRUCTURAL_ACTIONS = "on_structural_actions"
    """Run cleanup only when the feedback batch contained ``insert_node``, ``delete_node``, or ``move_node``."""

    ON_MOVE_ACTIONS = "on_move_actions"
    """Run cleanup only when the feedback batch contained ``move_node``. Inserts and deletes alone do not trigger it."""


# ---------------------------------------------------------------------------
# Factory functions — translate enum values into live strategy instances.
# Imports are deferred inside each factory to avoid circular dependencies
# between the config package and the _actor package.
# ---------------------------------------------------------------------------


def make_redaction_strategy(option: RedactionStrategyOption):  # type: ignore[return]
    """Return a ``RedactionStrategy`` instance for *option*."""
    from .._actor._redaction import DefaultRedactionStrategy, NoRedactionStrategy

    match option:
        case RedactionStrategyOption.DEFAULT:
            return DefaultRedactionStrategy()
        case RedactionStrategyOption.NONE:
            return NoRedactionStrategy()


def make_prompt_render_strategy(option: PromptRenderStrategyOption):  # type: ignore[return]
    """Return a ``RenderPromptStrategy`` instance for *option*."""
    from .._actor._render_prompt_strategy import JsonRenderPromptStrategy, MarkdownRenderPromptStrategy, XmlRenderPromptStrategy

    match option:
        case PromptRenderStrategyOption.XML:
            return XmlRenderPromptStrategy()
        case PromptRenderStrategyOption.JSON:
            return JsonRenderPromptStrategy()
        case PromptRenderStrategyOption.MARKDOWN:
            return MarkdownRenderPromptStrategy()


def make_signal_render_strategy(option: SignalRenderStrategyOption):  # type: ignore[return]
    """Return a ``SignalRenderingStrategy`` instance for *option*."""
    from .._actor._signal_rendering_strategy import DefaultSignalRenderingStrategy, JsonSignalRenderingStrategy, XmlSignalRenderingStrategy

    match option:
        case SignalRenderStrategyOption.MARKDOWN:
            return DefaultSignalRenderingStrategy()
        case SignalRenderStrategyOption.JSON:
            return JsonSignalRenderingStrategy()
        case SignalRenderStrategyOption.XML:
            return XmlSignalRenderingStrategy()


def make_structural_cleanup_predicate(option: StructuralCleanupOption):  # type: ignore[return]
    """Return a ``StructuralCleanupPredicate`` callable for *option*."""
    from .._actor._structural_strategy import (
        always_cleanup_structure,
        cleanup_structure_on_move_actions,
        cleanup_structure_on_structural_actions,
        never_cleanup_structure,
    )

    match option:
        case StructuralCleanupOption.ALWAYS:
            return always_cleanup_structure
        case StructuralCleanupOption.NEVER:
            return never_cleanup_structure
        case StructuralCleanupOption.ON_STRUCTURAL_ACTIONS:
            return cleanup_structure_on_structural_actions
        case StructuralCleanupOption.ON_MOVE_ACTIONS:
            return cleanup_structure_on_move_actions
