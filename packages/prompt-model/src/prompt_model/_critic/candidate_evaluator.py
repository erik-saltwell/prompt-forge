from __future__ import annotations

import asyncio

from .._llm import acomplete
from .._metrics import EvalCase, Metric, MetricResult
from ..config import LiteLLMConfig
from .composite_scorer import CompositeScorer
from .selection_data import _SelectionData


async def evaluate_candidate(
    selection_data: _SelectionData,
    inputs: list[EvalCase],
    execution_config: LiteLLMConfig,
    metrics: list[Metric],
    scorer: CompositeScorer,
) -> None:
    if not metrics:
        raise ValueError("evaluate_candidate requires at least one metric")
    if not selection_data.has_cases:
        raise ValueError("evaluate candidate requires a candidate with untested inputs")

    complete: bool = False
    case_id: int = selection_data.start_evaluation()

    try:
        prompt_text: str = selection_data.candidate.prompt.to_markdown()
        eval_case: EvalCase = inputs[case_id]
        output: str = await acomplete(prompt_text, eval_case.input, execution_config)
        raw_results: list[MetricResult | BaseException] = await asyncio.gather(
            *(m.evaluate(prompt_text, eval_case.input, output, eval_case.ground_truth) for m in metrics),
            return_exceptions=True,
        )
        metric_results: list[MetricResult] = []
        for result in raw_results:
            if isinstance(result, BaseException):
                raise result
            metric_results.append(result)
        score: float
        if not metric_results:
            # A metric returns an empty result list when it found no issues. When every metric
            # is clean for this case there is nothing to score, so we award a perfect 1.0.
            score = 1.0
        else:
            score = scorer.compute(metric_results)
        selection_data.complete_evaluation(metric_results, score)
        complete = True
    finally:
        if not complete:
            selection_data.rollback_evaluation(case_id)
