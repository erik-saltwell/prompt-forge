"""Load YAML scenario files into EvalCase objects for hybrid-judge evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from prompt_model._prompt import parse_from_string
from prompt_model.config import EvalCase
from prompt_model.strategies.prompt_rendering_strategy import XmlRenderPromptStrategy

_XML_RENDERER: XmlRenderPromptStrategy = XmlRenderPromptStrategy()


def _build_input(
    prompt_markdown: str,
    case_input: str,
    model_output: str,
    assessment: str,
    ground_truth: str | None,
) -> str:
    """Build the judge user-message string from scenario components.

    Replicates the format produced by HybridMetric.judge_user_prompt using
    XmlRenderPromptStrategy — matching the updated _run_judge rendering path.
    """
    tree = parse_from_string(prompt_markdown)
    xml_tree: str = _XML_RENDERER.render(tree, focus_ids=None)
    gt_block: str = f"\n\n<ground_truth>\n{ground_truth}\n</ground_truth>" if ground_truth is not None else ""
    return (
        f"<prompt>\n{xml_tree}\n</prompt>\n\n"
        f"<case_input>\n{case_input}\n</case_input>\n\n"
        f"<model_output>\n{model_output}\n</model_output>"
        f"{gt_block}\n\n"
        f"<assessment>\n{assessment}\n</assessment>"
    )


def load_scenario(path: Path) -> EvalCase:
    """Load a single YAML scenario file into an EvalCase."""
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))

    input_str: str = _build_input(
        prompt_markdown=data["prompt_markdown"],
        case_input=data["case_input"],
        model_output=data["model_output"],
        assessment=data["assessment"],
        ground_truth=data.get("ground_truth"),
    )
    ground_truth: str = json.dumps(
        {
            "golden_diagnosis": data.get("golden_diagnosis", {}),
            "criteria": data.get("criteria", {}),
        },
        ensure_ascii=False,
    )
    return EvalCase(input=input_str, ground_truth=ground_truth)


def load_all_scenarios(scenarios_dir: Path) -> list[EvalCase]:
    """Load all YAML files from the scenarios directory, sorted by filename."""
    return [load_scenario(p) for p in sorted(scenarios_dir.glob("*.yaml"))]
