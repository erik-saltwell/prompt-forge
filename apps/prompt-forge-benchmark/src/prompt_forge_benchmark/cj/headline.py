"""Post-hoc weighted-F1 evaluation for a CJ prompt against the test set.

This is the SCULPT-equivalent reporting pass: take a final optimized prompt,
run it against every test case, parse outputs with the SCULPT-compatible
parser, and compute the corpus-level metrics that the SCULPT paper reports
(weighted F1, accuracy, per-class precision/recall).

Kept separate from the optimizer's per-case metric so corpus-only statistics
do not contaminate the per-case `Metric` contract.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import litellm
from prompt_model.config import EvalCase, LiteLLMConfig
from prompt_model_metrics.benchmarking import parse_yes_no
from sklearn.metrics import classification_report, f1_score


@dataclass(frozen=True, slots=True)
class HeadlineReport:
    weighted_f1: float
    accuracy: float
    n_cases: int
    n_unparseable: int
    classification_report: str
    predictions: list[str]
    ground_truths: list[str]


# Sentinel for "the model output could not be parsed as yes/no". We map it to
# a third pseudo-label so sklearn metrics treat it as wrong without crashing.
_UNPARSEABLE: str = "__unparseable__"


async def _predict(
    system_prompt: str,
    case: EvalCase,
    target_llm: LiteLLMConfig,
    sem: asyncio.Semaphore,
) -> str:
    async with sem:
        kwargs: dict[str, Any] = target_llm.to_completion_kwargs()
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": case.input},
        ]
        response = await litellm.acompletion(**kwargs)
        content: str = response.choices[0].message.content or ""
    parsed: str | None = parse_yes_no(content)
    return parsed if parsed is not None else _UNPARSEABLE


async def evaluate_prompt(
    prompt: str,
    cases: list[EvalCase],
    target_llm: LiteLLMConfig,
    max_concurrency: int = 8,
) -> HeadlineReport:
    """Run ``prompt`` against every case and compute corpus-level metrics.

    ``weighted_f1`` is sklearn's weighted F1 — the SCULPT headline. ``n_unparseable``
    counts outputs that did not collapse to "yes" or "no" through the SCULPT parser.
    """
    sem: asyncio.Semaphore = asyncio.Semaphore(max_concurrency)
    predictions: list[str] = await asyncio.gather(*(_predict(prompt, c, target_llm, sem) for c in cases))
    ground_truths: list[str] = [(c.ground_truth or "").lower().strip() for c in cases]

    n_correct: int = sum(1 for p, g in zip(predictions, ground_truths, strict=True) if p == g)
    n_unparseable: int = sum(1 for p in predictions if p == _UNPARSEABLE)
    accuracy: float = n_correct / len(cases) if cases else 0.0

    weighted_f1: float = float(f1_score(ground_truths, predictions, labels=["yes", "no"], average="weighted", zero_division=0.0))
    report: str = classification_report(
        ground_truths,
        predictions,
        labels=["yes", "no"],
        zero_division=0.0,
    )

    return HeadlineReport(
        weighted_f1=weighted_f1,
        accuracy=accuracy,
        n_cases=len(cases),
        n_unparseable=n_unparseable,
        classification_report=report,
        predictions=predictions,
        ground_truths=ground_truths,
    )
