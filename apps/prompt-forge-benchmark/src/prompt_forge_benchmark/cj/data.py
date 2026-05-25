"""Load SCULPT's Causal Judgement (CJ) data, vendored under apps/prompt-forge-benchmark/data/.

TSV format: two tab-separated columns per line — Scenario, Answer ("Yes" | "No").
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from prompt_model.config import EvalCase

type Split = Literal["train", "val", "test"]

_DATA_ROOT: Path = Path(__file__).resolve().parents[3] / "data" / "causal_judgement"
_SPLIT_FILES: dict[Split, str] = {
    "train": "train.tsv",
    "val": "validation.tsv",
    "test": "test.tsv",
}


def initial_prompt_path() -> Path:
    return _DATA_ROOT / "initial_prompt.md"


def load_initial_prompt() -> str:
    return initial_prompt_path().read_text()


def load_split(split: Split) -> list[EvalCase]:
    """Read one TSV split and return prompt-model EvalCase objects.

    Ground truth is normalised to lowercase ("yes" / "no") so the metric's
    case-insensitive compare can stay one-line.
    """
    path: Path = _DATA_ROOT / _SPLIT_FILES[split]
    cases: list[EvalCase] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        parts: list[str] = line.split("\t")
        if len(parts) < 2:
            continue
        scenario: str = parts[0]
        answer: str = parts[-1].strip().lower()
        cases.append(EvalCase(input=scenario, ground_truth=answer))
    return cases
