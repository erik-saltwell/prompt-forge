"""Load YAML scenario files into EvalCase objects for feedback-actor evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from prompt_model._prompt import parse_from_string
from prompt_model._rendering import XmlRenderPromptStrategy
from prompt_model.config import EvalCase

_XML_RENDERER: XmlRenderPromptStrategy = XmlRenderPromptStrategy()


def _format_signals(signals: list[dict[str, Any]]) -> str:
    """Format a list of signal dicts into the DefaultSignalRenderingStrategy markdown format.

    All signals are assumed to share the same culprit_node_id (one-bucket-per-actor-call
    production design). If they differ, each group gets its own heading.
    """
    if not signals:
        return "(no feedback signals)"

    # Group by culprit_node_id preserving order
    groups: dict[str, list[dict[str, Any]]] = {}
    for sig in signals:
        nid: str = str(sig["culprit_node_id"])
        groups.setdefault(nid, []).append(sig)

    parts: list[str] = []
    for node_id, group_signals in groups.items():
        lines: list[str] = [f"# Issues affecting node `{node_id}`"]
        for i, sig in enumerate(group_signals, start=1):
            lines.append("")
            n: int = int(sig.get("seen_in_n_cases", 1))
            header: str = f"## Issue {i}" + (f" (seen in {n} cases)" if n > 1 else "")
            lines.append(header)
            lines.append(f"**What's wrong:** {sig['rationale']}")
            lines.append(f"**Target behavior:** {sig['target_behavior']}")
            lines.append(f"**Success criterion:** {sig['success_criterion']}")
            if sig.get("suggested_prompt_change"):
                lines.append(f"**Suggested change:** {sig['suggested_prompt_change']}")
            lines.append(f"**Evidence — input:** {sig['input_snippet']}")
            lines.append(f"**Evidence — output:** {sig['output_snippet']}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _build_input(prompt_markdown: str, signals: list[dict[str, Any]], preserve: list[str]) -> str:
    """Build the actor user-message string from scenario components.

    Replicates the format produced by revise._build_user_prompt using XmlRenderPromptStrategy
    and DefaultSignalRenderingStrategy.
    """
    tree = parse_from_string(prompt_markdown)
    xml_tree: str = _XML_RENDERER.render(tree, focus_ids=None)
    rendered_signals: str = _format_signals(signals)
    preserve_block: str = "\n".join(f"- {p}" for p in preserve) if preserve else "(none)"
    return f"<prompt>\n{xml_tree}\n</prompt>\n\n<feedback>\n{rendered_signals}\n</feedback>\n\n<preserve>\n{preserve_block}\n</preserve>"


def load_scenario(path: Path) -> EvalCase:
    """Load a single YAML scenario file into an EvalCase."""
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))

    input_str: str = _build_input(
        prompt_markdown=data["prompt_markdown"],
        signals=data.get("signals", []),
        preserve=data.get("preserve", []),
    )
    ground_truth: str = json.dumps(
        {
            "golden_actions": data.get("golden_actions", {"reasoning": "", "actions": []}),
            "criteria": data.get("criteria", {}),
        },
        ensure_ascii=False,
    )
    return EvalCase(input=input_str, ground_truth=ground_truth)


def load_all_scenarios(scenarios_dir: Path) -> list[EvalCase]:
    """Load all YAML files from the scenarios directory, sorted by filename."""
    return [load_scenario(p) for p in sorted(scenarios_dir.glob("*.yaml"))]
