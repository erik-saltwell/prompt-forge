"""Load YAML scenario files into EvalCase objects for structural-actor evaluation.

Each scenario YAML carries:
  - prompt_markdown: the post-revision prompt tree the structural actor inspects
  - preserve: list of preserve-guardrail strings (may be empty)
  - defects: list of planted-defect dicts (may be empty for clean-tree cases)

The loader assembles the actor's user-message input (`<prompt>` XML + `<preserve>`)
and serializes `{"defects": [...]}` as the ground_truth string. The four
structural-actor metrics read `defects` from ground_truth.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from prompt_model._prompt import parse_from_string
from prompt_model.config import EvalCase
from prompt_model.strategies.prompt_rendering_strategy import XmlRenderPromptStrategy

_XML_RENDERER: XmlRenderPromptStrategy = XmlRenderPromptStrategy()


def _build_input(prompt_markdown: str, preserve: list[str]) -> str:
    """Build the actor user-message string from scenario components.

    Mirrors `_structural_actor._build_user_prompt`: <prompt> XML + <preserve> bullets.
    """
    tree = parse_from_string(prompt_markdown)
    xml_tree: str = _XML_RENDERER.render(tree, focus_ids=None)
    preserve_block: str = "\n".join(f"- {p}" for p in preserve) if preserve else "(none)"
    return f"<prompt>\n{xml_tree}\n</prompt>\n\n<preserve>\n{preserve_block}\n</preserve>"


def load_scenario(path: Path) -> EvalCase:
    """Load a single YAML scenario file into an EvalCase."""
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))

    input_str: str = _build_input(
        prompt_markdown=data["prompt_markdown"],
        preserve=data.get("preserve", []),
    )
    ground_truth: str = json.dumps({"defects": data.get("defects", [])}, ensure_ascii=False)
    return EvalCase(input=input_str, ground_truth=ground_truth)


def load_all_scenarios(scenarios_dir: Path) -> list[EvalCase]:
    """Load all YAML files from the scenarios directory, sorted by filename."""
    return [load_scenario(p) for p in sorted(scenarios_dir.glob("*.yaml"))]
