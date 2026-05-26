from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Protocol
from xml.sax.saxutils import escape, quoteattr

from ._resources import load_rendering_resource

if TYPE_CHECKING:
    from .._metrics._aggregator import AggregatedNodeBucket
    from .._metrics.result import IssueSignal


class SignalRenderingStrategy(Protocol):
    """Renders one bucket of `IssueSignal`s as the string the actor LLM reads,
    and describes its own rendering convention via `describe_format()`.
    """

    def render(self, bucket: AggregatedNodeBucket) -> str: ...

    def describe_format(self) -> str: ...


class _ResourceFormatDescription:
    """Mixin: `describe_format()` loads `format_snippet_resource` from
    `_resources/signal_format/<name>.md`.
    """

    format_snippet_resource: ClassVar[str]

    def describe_format(self) -> str:
        return load_rendering_resource("signal_format", self.format_snippet_resource)


class DefaultSignalRenderingStrategy(_ResourceFormatDescription):
    """Renders one bucket of `IssueSignal`s as humanized markdown for the actor
    LLM. One `## Issue N` subsection per signal, with labeled fields.
    """

    format_snippet_resource: ClassVar[str] = "default"

    def render(self, bucket: AggregatedNodeBucket) -> str:
        lines: list[str] = [f"# Issues affecting node `{bucket.culprit_node_id}`"]
        for i, signal in enumerate(bucket.signals, start=1):
            lines.append("")
            lines.extend(_render_markdown_signal(i, signal))
        return "\n".join(lines)


class JsonSignalRenderingStrategy(_ResourceFormatDescription):
    """Renders the bucket as pretty-printed JSON via Pydantic."""

    format_snippet_resource: ClassVar[str] = "json"

    def render(self, bucket: AggregatedNodeBucket) -> str:
        return bucket.model_dump_json(indent=2)


class XmlSignalRenderingStrategy(_ResourceFormatDescription):
    """Renders the bucket as XML with `<signal>` children carrying field
    elements. Mirrors the actor's prompt rendering format so both inputs feel
    structurally consistent to the LLM.
    """

    format_snippet_resource: ClassVar[str] = "xml"

    def render(self, bucket: AggregatedNodeBucket) -> str:
        lines: list[str] = [f"<bucket culprit_node_id={quoteattr(bucket.culprit_node_id)}>"]
        for signal in bucket.signals:
            lines.extend(_render_xml_signal(signal, "  "))
        lines.append("</bucket>")
        return "\n".join(lines)


def _render_markdown_signal(index: int, signal: IssueSignal) -> list[str]:
    header: str = f"## Issue {index}"
    if signal.seen_in_n_cases > 1:
        header += f" (seen in {signal.seen_in_n_cases} cases)"
    lines: list[str] = [
        header,
        f"**What's wrong:** {signal.rationale}",
        f"**Target behavior:** {signal.target_behavior}",
        f"**Success criterion:** {signal.success_criterion}",
    ]
    if signal.suggested_prompt_change:
        lines.append(f"**Suggested change:** {signal.suggested_prompt_change}")
    lines.append(f"**Evidence — input:** {signal.input_snippet}")
    lines.append(f"**Evidence — output:** {signal.output_snippet}")
    return lines


def _render_xml_signal(signal: IssueSignal, indent: str) -> list[str]:
    lines: list[str] = [f'{indent}<signal seen_in_n_cases="{signal.seen_in_n_cases}">']
    inner: str = indent + "  "
    lines.append(f"{inner}<rationale>{escape(signal.rationale)}</rationale>")
    lines.append(f"{inner}<target_behavior>{escape(signal.target_behavior)}</target_behavior>")
    lines.append(f"{inner}<success_criterion>{escape(signal.success_criterion)}</success_criterion>")
    if signal.suggested_prompt_change:
        lines.append(f"{inner}<suggested_prompt_change>{escape(signal.suggested_prompt_change)}</suggested_prompt_change>")
    lines.append(f"{inner}<input_snippet>{escape(signal.input_snippet)}</input_snippet>")
    lines.append(f"{inner}<output_snippet>{escape(signal.output_snippet)}</output_snippet>")
    lines.append(f"{indent}</signal>")
    return lines
