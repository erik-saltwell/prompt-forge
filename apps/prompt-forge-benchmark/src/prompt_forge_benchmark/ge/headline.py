"""Post-hoc multi-label F1 evaluation for a GoEmotions prompt against the test set.

Reports the SCULPT-equivalent corpus headline numbers (macro F1, micro F1,
weighted F1, exact-match accuracy) on a held-out test split. Kept separate
from the per-case ``GoEmotionsMultiLabelF1`` metric so corpus-level statistics
do not contaminate the per-case ``Metric`` contract.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import litellm
import numpy as np
from prompt_model.config import EvalCase, LiteLLMConfig
from prompt_model_metrics.benchmarking import EMOTION_LABELS, parse_emotions, parse_label_string
from sklearn.metrics import classification_report, f1_score

_LABEL_ORDER: list[str] = sorted(EMOTION_LABELS)


@dataclass(frozen=True, slots=True)
class HeadlineReport:
    macro_f1: float
    micro_f1: float
    weighted_f1: float
    exact_match_accuracy: float
    n_cases: int
    n_unparseable: int
    classification_report: str
    predictions: list[set[str]]
    ground_truths: list[set[str]]


async def _predict(
    system_prompt: str,
    case: EvalCase,
    target_llm: LiteLLMConfig,
    sem: asyncio.Semaphore,
) -> set[str]:
    async with sem:
        kwargs: dict[str, Any] = target_llm.to_completion_kwargs()
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": case.input},
        ]
        response = await litellm.acompletion(**kwargs)
        content: str = response.choices[0].message.content or ""
    return parse_emotions(content)


def _binarize(label_sets: list[set[str]]) -> np.ndarray:
    """Convert a list of label-sets to a (n_cases x n_labels) 0/1 matrix."""
    mat: np.ndarray = np.zeros((len(label_sets), len(_LABEL_ORDER)), dtype=int)
    label_to_idx: dict[str, int] = {label: i for i, label in enumerate(_LABEL_ORDER)}
    for row, labels in enumerate(label_sets):
        for label in labels:
            if label in label_to_idx:
                mat[row, label_to_idx[label]] = 1
    return mat


async def evaluate_prompt(
    prompt: str,
    cases: list[EvalCase],
    target_llm: LiteLLMConfig,
    max_concurrency: int = 8,
) -> HeadlineReport:
    """Run ``prompt`` against every case and compute corpus-level multi-label F1."""
    sem: asyncio.Semaphore = asyncio.Semaphore(max_concurrency)
    predictions: list[set[str]] = await asyncio.gather(*(_predict(prompt, c, target_llm, sem) for c in cases))
    ground_truths: list[set[str]] = [parse_label_string(c.ground_truth or "") for c in cases]

    n_unparseable: int = sum(1 for p in predictions if not p)
    n_exact: int = sum(1 for p, g in zip(predictions, ground_truths, strict=True) if p == g)
    exact_match: float = n_exact / len(cases) if cases else 0.0

    y_true: np.ndarray = _binarize(ground_truths)
    y_pred: np.ndarray = _binarize(predictions)

    macro_f1: float = float(f1_score(y_true, y_pred, average="macro", zero_division=0.0))
    micro_f1: float = float(f1_score(y_true, y_pred, average="micro", zero_division=0.0))
    weighted_f1: float = float(f1_score(y_true, y_pred, average="weighted", zero_division=0.0))
    report: str = classification_report(y_true, y_pred, target_names=_LABEL_ORDER, zero_division=0.0)

    return HeadlineReport(
        macro_f1=macro_f1,
        micro_f1=micro_f1,
        weighted_f1=weighted_f1,
        exact_match_accuracy=exact_match,
        n_cases=len(cases),
        n_unparseable=n_unparseable,
        classification_report=report,
        predictions=predictions,
        ground_truths=ground_truths,
    )
