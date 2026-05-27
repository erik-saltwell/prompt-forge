"""Per-case multi-label F1 metric for GoEmotions.

Score: per-case F1 between the predicted emotion set and the ground-truth set,
computed as ``2 * |P ∩ G| / (|P| + |G|)``. Empty prediction *and* empty ground
truth → score 1.0 (both agree on no labels). Empty prediction with non-empty
ground truth → score 0.0.

The parser is permissive: it scans the model output for any token matching a
known emotion label (case-insensitive), tolerating punctuation and surrounding
prose. Outputs that contain no recognized label produce an empty predicted set.

Corpus-level macro/micro F1 is computed separately in the headline pass —
this metric is per-case so it composes with the optimizer's per-case ``Metric``
contract.
"""

from __future__ import annotations

import re
from typing import ClassVar

from prompt_model import HybridMetric, MissingGroundTruthError

EMOTION_LABELS: frozenset[str] = frozenset(
    {
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
    }
)

_TOKEN_RE: re.Pattern[str] = re.compile(r"[a-zA-Z]+")


def parse_emotions(raw: str) -> set[str]:
    """Return the set of recognized emotion labels found in raw output.

    Tokenizes on alphabetic runs (so commas, periods, and surrounding prose are
    ignored) and keeps every token that lower-cases to a known label.
    """
    tokens: list[str] = _TOKEN_RE.findall(raw)
    return {t.lower() for t in tokens if t.lower() in EMOTION_LABELS}


def parse_label_string(raw: str) -> set[str]:
    """Parse the ground-truth label string (comma-separated) into a set."""
    return {t.strip().lower() for t in raw.split(",") if t.strip().lower() in EMOTION_LABELS}


def _truncate(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


class GoEmotionsMultiLabelF1(HybridMetric):
    """Per-case multi-label F1 for GoEmotions."""

    name: ClassVar[str] = "ge_multilabel_f1"
    description: ClassVar[str] = (
        "GoEmotions multi-label F1: per-case F1 between the predicted and gold emotion sets, using a permissive label parser."
    )

    def score_case(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> tuple[float, str]:
        if ground_truth is None:
            raise MissingGroundTruthError("GoEmotionsMultiLabelF1 requires ground_truth on every EvalCase")

        gold: set[str] = parse_label_string(ground_truth)
        predicted: set[str] = parse_emotions(output)

        if not gold and not predicted:
            return 1.0, "Both predicted and gold label sets are empty (perfect agreement on no-emotion)."
        if not predicted:
            return 0.0, f"No recognized emotion labels in output (got: '{_truncate(output)}'). Expected: {sorted(gold)}."
        if not gold:
            return 0.0, f"Predicted {sorted(predicted)} but ground-truth set is empty."

        tp: int = len(predicted & gold)
        precision: float = tp / len(predicted) if predicted else 0.0
        recall: float = tp / len(gold) if gold else 0.0
        if precision + recall == 0.0:
            f1: float = 0.0
        else:
            f1 = 2.0 * precision * recall / (precision + recall)

        if f1 == 1.0:
            return 1.0, f"Exact match on labels: {sorted(gold)}."
        return (
            f1,
            f"F1={f1:.3f} (precision={precision:.2f}, recall={recall:.2f}). Predicted {sorted(predicted)}; gold {sorted(gold)}.",
        )
