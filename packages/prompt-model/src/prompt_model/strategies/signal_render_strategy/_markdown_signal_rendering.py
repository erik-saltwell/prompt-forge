from __future__ import annotations

from typing import ClassVar

from ..._metrics._aggregator import AggregatedNodeBucket
from ..._metrics.result import IssueSignal
from ._resources import load_rendering_resource


class MarkdownSignalRenderingStrategy:
    """Renders one bucket of `IssueSignal`s as humanized markdown for the actor
    LLM. One `## Issue N` subsection per signal, with labeled fields.
    """

    format_snippet_resource: ClassVar[str] = "markdown"

    def describe_format(self) -> str:
        return load_rendering_resource(self.format_snippet_resource)

    def render(self, bucket: AggregatedNodeBucket) -> str:
        lines: list[str] = [f"# Issues affecting node `{bucket.culprit_node_id}`"]
        for i, signal in enumerate(bucket.signals, start=1):
            lines.append("")
            lines.extend(_render_markdown_signal(i, signal))
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
