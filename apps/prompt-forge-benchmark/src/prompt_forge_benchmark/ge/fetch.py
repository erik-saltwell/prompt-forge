"""Fetch and sample GoEmotions splits, writing tab-separated files to the data dir.

Run once via ``python -m prompt_forge_benchmark.ge.fetch`` (or implicitly the
first time ``load_split`` finds a split missing). Subsequent runs read the
cached TSVs.

Default split sizes mirror the CJ benchmark's tractable scale (~160 total):
- train: 20 examples
- validation: 40 examples
- test: 100 examples

Override with ``--train``/``--val``/``--test`` to write larger splits. A fixed
seed (42) keeps the sample reproducible.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any

_DEFAULT_SIZES: dict[str, int] = {"train": 20, "validation": 40, "test": 100}
_SEED: int = 42

# GoEmotions emotion list (simplified config; 28 labels in this order)
EMOTION_LABELS: list[str] = [
    "admiration",
    "amusement",
    "anger",
    "annoyance",
    "approval",
    "caring",
    "confusion",
    "curiosity",
    "desire",
    "disappointment",
    "disapproval",
    "disgust",
    "embarrassment",
    "excitement",
    "fear",
    "gratitude",
    "grief",
    "joy",
    "love",
    "nervousness",
    "optimism",
    "pride",
    "realization",
    "relief",
    "remorse",
    "sadness",
    "surprise",
    "neutral",
]


def _write_split(rows: list[dict[str, Any]], path: Path) -> None:
    """Write a list of {text, labels: list[int]} dicts to a TSV at path."""
    lines: list[str] = []
    for row in rows:
        text: str = str(row["text"]).replace("\t", " ").replace("\n", " ").strip()
        label_ids: list[int] = list(row["labels"])
        label_names: list[str] = [EMOTION_LABELS[i] for i in label_ids if 0 <= i < len(EMOTION_LABELS)]
        labels_str: str = ",".join(label_names) if label_names else "neutral"
        lines.append(f"{text}\t{labels_str}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def ensure_splits(data_root: Path, sizes: dict[str, int] | None = None) -> None:
    """Download GoEmotions via HuggingFace and write sampled TSVs to data_root.

    Idempotent — only writes splits whose TSV files don't yet exist. Cleans up
    nothing.
    """
    sizes = sizes or _DEFAULT_SIZES
    targets: dict[str, Path] = {
        "train": data_root / "train.tsv",
        "validation": data_root / "validation.tsv",
        "test": data_root / "test.tsv",
    }
    missing: dict[str, Path] = {k: v for k, v in targets.items() if not v.exists()}
    if not missing:
        return

    # Lazy import — the `datasets` dep is only needed on first fetch.
    from datasets import load_dataset  # type: ignore[import-untyped]

    print(f"Fetching GoEmotions from HuggingFace ({len(missing)} split(s) missing)...", file=sys.stderr, flush=True)
    ds: Any = load_dataset("go_emotions", "simplified")
    rng: random.Random = random.Random(_SEED)
    for split_name, path in missing.items():
        full: Any = ds[split_name]
        n: int = min(sizes[split_name], len(full))
        indices: list[int] = rng.sample(range(len(full)), n)
        rows: list[dict[str, Any]] = [full[i] for i in indices]
        _write_split(rows, path)
        print(
            f"  wrote {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path} ({n} rows)", file=sys.stderr, flush=True
        )


def main() -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="prompt_forge_benchmark.ge.fetch",
        description="Fetch and sample GoEmotions splits into data/go_emotions/*.tsv.",
    )
    parser.add_argument("--train", type=int, default=_DEFAULT_SIZES["train"])
    parser.add_argument("--val", type=int, default=_DEFAULT_SIZES["validation"])
    parser.add_argument("--test", type=int, default=_DEFAULT_SIZES["test"])
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even if TSV files already exist.",
    )
    args = parser.parse_args()

    data_root: Path = Path(__file__).resolve().parents[3] / "data" / "go_emotions"
    if args.force:
        for fname in ("train.tsv", "validation.tsv", "test.tsv"):
            (data_root / fname).unlink(missing_ok=True)
    ensure_splits(data_root, sizes={"train": args.train, "validation": args.val, "test": args.test})
    return 0


if __name__ == "__main__":
    sys.exit(main())
