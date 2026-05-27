"""Load YAML scenario files into EvalCase objects for the g_eval_factory target.

Each scenario describes one criterion the factory must build a G-Eval judging
context for, along with the hand-labeled `requires_ground_truth` answer.

Scenarios live under either `scenarios/train/` (used during optimization) or
`scenarios/holdout/` (reserved for after-the-fact validation — never enters the
optimizer loop). The default loader returns the training split.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from prompt_model.config import EvalCase


def load_scenario(path: Path) -> EvalCase:
    """Load a single YAML scenario into an EvalCase."""
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    criterion: str = data["criterion"]
    label: bool = bool(data["requires_ground_truth_expected"])
    ground_truth: str = json.dumps({"requires_ground_truth": label}, ensure_ascii=False)
    return EvalCase(input=criterion, ground_truth=ground_truth)


def load_all_scenarios(scenarios_dir: Path, split: str = "train") -> list[EvalCase]:
    """Load all YAML files from `<scenarios_dir>/<split>/`, sorted by filename."""
    split_dir: Path = scenarios_dir / split
    if not split_dir.is_dir():
        return []
    return [load_scenario(p) for p in sorted(split_dir.glob("*.yaml"))]
