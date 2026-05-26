from __future__ import annotations

from typing import ClassVar
from xml.sax.saxutils import escape, quoteattr

from ..._metrics._aggregator import AggregatedNodeBucket
from ..._metrics.result import IssueSignal
from ._resources import load_rendering_resource


class XmlSignalRenderingStrategy:
    """Renders the bucket as XML with `<signal>` children carrying field
    elements. Mirrors the actor's prompt rendering format so both inputs feel
    structurally consistent to the LLM.
    """

    format_snippet_resource: ClassVar[str] = "xml"

    def describe_format(self) -> str:
        return load_rendering_resource(self.format_snippet_resource)

    def render(self, bucket: AggregatedNodeBucket) -> str:
        lines: list[str] = [f"<bucket culprit_node_id={quoteattr(bucket.culprit_node_id)}>"]
        for signal in bucket.signals:
            lines.extend(_render_xml_signal(signal, "  "))
        lines.append("</bucket>")
        return "\n".join(lines)


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
