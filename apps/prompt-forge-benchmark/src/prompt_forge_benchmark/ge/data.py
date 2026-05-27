"""Load SCULPT-style GoEmotions data, vendored as TSVs under data/go_emotions/.

TSV format: two tab-separated columns per line — `text`, `labels` (comma-separated
emotion names, e.g. ``joy,gratitude``; ``neutral`` if no strong emotion).

If a split file is missing on first use, ``fetch.py`` is called to download it
from HuggingFace's ``go_emotions`` (simplified config) and write the TSV.
Splits are sampled small by default to match the CJ benchmark's tractability:
the file written by ``fetch.py`` already carries the sampled split.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from prompt_model.config import EvalCase

from .fetch import ensure_splits

type Split = Literal["train", "val", "test"]

_DATA_ROOT: Path = Path(__file__).resolve().parents[3] / "data" / "go_emotions"
_SPLIT_FILES: dict[Split, str] = {
    "train": "train.tsv",
    "val": "validation.tsv",
    "test": "test.tsv",
}


def initial_prompt_path() -> Path:
    return _DATA_ROOT / "initial_prompt.md"


def load_initial_prompt() -> str:
    return initial_prompt_path().read_text()


def _split_path(split: Split) -> Path:
    return _DATA_ROOT / _SPLIT_FILES[split]


def load_split(split: Split) -> list[EvalCase]:
    """Read one TSV split and return EvalCase objects.

    Ground truth is the verbatim comma-separated label string (e.g. ``joy,gratitude``).
    The per-case metric splits it on commas at scoring time.
    """
    path: Path = _split_path(split)
    if not path.exists():
        ensure_splits(_DATA_ROOT)

    cases: list[EvalCase] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        parts: list[str] = line.split("\t")
        if len(parts) < 2:
            continue
        text: str = parts[0]
        labels: str = parts[-1].strip().lower()
        cases.append(EvalCase(input=text, ground_truth=labels))
    return cases
